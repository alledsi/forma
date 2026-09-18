"""
FORMA — Plateforme de génération de documents UM-ACEP.

Dev local :   python app.py
Production :  gunicorn -w 3 -b 0.0.0.0:4444 app:app
"""
import datetime
import os

from flask import Flask, render_template, request, jsonify, Response
from doc_engine import DOC_TYPES, generate_preview_html
from kyc_render import render_kyc_html, generate_kyc_pdf

app = Flask(__name__)


def _map_client_to_form(client):
    """Traduit les colonnes Oracle (kyc_data) vers les clés de champ du formulaire."""
    secteur = client.get("LIB_SECT") or client.get("LIB_SSECT") or ""
    return {
        "matricule_client": client.get("MATRICULE_CLIENT", ""),
        "code_bureau": client.get("CODE_BUREAU", ""),
        "raison_sociale": client.get("RAISON_SOCIALE_CLIENT", ""),
        "statut_client": client.get("STATUT_CLIENT", ""),
        "sigle": client.get("SIGLE_CLIENT", ""),
        "date_creation": client.get("DATE_CRE", ""),
        "forme_juridique": client.get("LIBELLE_FORME", ""),
        "agrement": "",
        "no_agrement": client.get("NO_AGREMENT", ""),
        "delivre_par": client.get("DELIVRE_PAR", ""),
        "no_registre_commerce": client.get("NO_REGISTRE_COMMERCE", ""),
        "date_deliv_registre": client.get("DATE_DELIV_RC", ""),
        "ninea": client.get("NINEA", ""),
        "date_deliv_ninea": client.get("DATE_DELIV_NINEA", ""),
        "sous_secteur": client.get("LIB_SSECT", ""),
        "secteur": secteur,
        "telephone": client.get("TEL_ENTREPRISE_FIXE", ""),
        "email": client.get("EMAIL", ""),
        "adresse": client.get("ADRESSE_1", ""),
        "adresse_postale": client.get("ADRESSE_POST", ""),
        "pays": client.get("LIB_PAYS", ""),
        "cotation": client.get("LIB_COTATION", ""),
        "nature": client.get("LIB_NATURE", ""),
        "categorie": client.get("INT_CATEGORIE", ""),
        "gestionnaire": client.get("NOM_GESTIONNAIRE", ""),
        "sms_connect": client.get("SMS_CONNECT", ""),
        "consentement": client.get("CONSENTEMENT", ""),
        "numero_consentement": client.get("NO_CONSENT", ""),
    }


def _map_signataire(row):
    return {
        "prenom": row.get("PRENOM", ""), "nom": row.get("NOM", ""),
        "fonction": row.get("FONCTIONS", ""),
        "piece_identite": row.get("NUMERO_PIECE_IDENTITE", ""),
        "nationalite": row.get("NATIONALITE", ""),
    }


def _map_actionnaire(row):
    return {
        "prenom": row.get("PRENOM", ""), "nom": row.get("NOM", ""),
        "piece_identite": row.get("NUMERO_PIECE_IDENTITE", ""),
        "part": row.get("PART", ""), "nationalite": row.get("NATIONALITE", ""),
    }


def _map_infos_fin(row):
    return {
        "annee": row.get("ANNEE", ""),
        "chiffre_affaires": row.get("CHIFFRE_AFFAIRE", ""),
        "resultat_net": row.get("RESULTAT_NET", ""),
        "capital": row.get("CAPITAL", ""),
        "effectif": row.get("EFFECTIF", ""),
    }


@app.route("/")
def index():
    # On n'envoie au front que ce qui est nécessaire (pas row_map/date_in_label_row)
    doc_types_public = {
        key: {
            "label": cfg["label"],
            "description": cfg.get("description", ""),
            "icon": cfg.get("icon", "📄"),
            "fields": cfg["fields"],
        }
        for key, cfg in DOC_TYPES.items()
    }
    return render_template("index.html", doc_types=doc_types_public)


@app.route("/preview", methods=["POST"])
def preview():
    """Retourne un aperçu HTML du document (pas de fichier téléchargeable)."""
    payload = request.get_json(force=True)
    doc_type = payload.get("type")
    data = payload.get("data", {})

    if doc_type not in DOC_TYPES:
        return jsonify({"error": "Type de document invalide"}), 400

    try:
        html, filename = generate_preview_html(doc_type, data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    return jsonify({"html": html, "filename": filename})


@app.route("/kyc/lookup", methods=["POST"])
def kyc_lookup():
    """Recherche un client personne morale dans Oracle ACE par matricule."""
    from kyc_data import get_kyc_data, ClientIntrouvable, ClientPersonnePhysique

    payload = request.get_json(force=True)
    matricule = (payload.get("matricule") or "").strip()
    if not matricule:
        return jsonify({"error": "Merci de saisir un matricule client."}), 400

    try:
        data = get_kyc_data(matricule)
    except ClientIntrouvable as e:
        return jsonify({"error": str(e)}), 404
    except ClientPersonnePhysique as e:
        return jsonify({"error": str(e)}), 400
    except RuntimeError as e:
        # Config Oracle absente (ORACLE_HOST/USER/PASSWORD non définis)
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        return jsonify({"error": f"Erreur de connexion à la base ACE : {e}"}), 500

    return jsonify({
        "client": _map_client_to_form(data["client"]),
        "signataires": [_map_signataire(r) for r in data["signataires"]],
        "dirigeants": [_map_signataire(r) for r in data["dirigeants"]],
        "actionnaires": [_map_actionnaire(r) for r in data["actionnaires"]],
        "infos_fin": [_map_infos_fin(r) for r in data["infos_fin"]],
    })


@app.route("/kyc/preview", methods=["POST"])
def kyc_preview():
    """Rend la fiche KYC en HTML à partir des données (éditées) envoyées par le formulaire."""
    payload = request.get_json(force=True)
    payload.setdefault("date_jour", datetime.date.today().strftime("%d/%m/%Y"))
    try:
        html_out = render_kyc_html(payload)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    return jsonify({"html": html_out})


@app.route("/kyc/pdf", methods=["POST"])
def kyc_pdf():
    """
    Génère la fiche KYC en PDF (via WeasyPrint) avec en-tête logo+ACEP et
    numérotation de pages répétés sur chaque page — impossible à obtenir avec
    l'impression navigateur classique utilisée pour les attestations.
    Le PDF est renvoyé inline (pas d'en-tête Content-Disposition: attachment)
    pour rester dans le même esprit "aperçu + impression" que le reste de FORMA.
    """
    payload = request.get_json(force=True)
    payload.setdefault("date_jour", datetime.date.today().strftime("%d/%m/%Y"))
    try:
        pdf_bytes = generate_kyc_pdf(payload)
    except Exception as e:
        return jsonify({"error": f"Erreur de génération du PDF : {e}"}), 500

    return Response(
        pdf_bytes,
        mimetype="application/pdf",
        headers={"Content-Disposition": "inline; filename=fiche_kyc.pdf"},
    )


def _kyc_error_page(message, status):
    """Petite page HTML d'erreur (plutôt qu'un JSON brut) : cette route est
    destinée à être ouverte comme un lien direct dans le navigateur."""
    body = f"""<!DOCTYPE html>
<html lang="fr"><head><meta charset="utf-8"><title>Fiche KYC</title></head>
<body style="font-family:Arial, sans-serif;padding:48px;color:#333;">
<h2 style="color:#b00020;margin-bottom:10px;">Impossible d'ouvrir la fiche KYC</h2>
<p>{_e_html(message)}</p>
</body></html>"""
    return Response(body, status=status, mimetype="text/html")


def _e_html(s):
    import html as _html
    return _html.escape(str(s))


@app.route("/kyc/pdf/<matricule>", methods=["GET"])
def kyc_pdf_by_matricule(matricule):
    """
    Lien direct : GET /kyc/pdf/<matricule> va chercher les données du client
    dans Oracle ACE et ouvre directement le PDF de sa fiche KYC, sans passer
    par l'écran de recherche/édition (utile pour être appelé depuis un autre
    outil ACEP). Contrairement au parcours normal, les données ne sont donc
    pas relues/éditées avant impression ici : elles sortent telles quelles de
    la base.
    """
    from kyc_data import get_kyc_data, ClientIntrouvable, ClientPersonnePhysique

    matricule = (matricule or "").strip()
    if not matricule:
        return _kyc_error_page("Merci de préciser un matricule client dans le lien.", 400)

    try:
        raw = get_kyc_data(matricule)
    except ClientIntrouvable as e:
        return _kyc_error_page(str(e), 404)
    except ClientPersonnePhysique as e:
        return _kyc_error_page(str(e), 400)
    except RuntimeError as e:
        return _kyc_error_page(str(e), 500)
    except Exception as e:
        return _kyc_error_page(f"Erreur de connexion à la base ACE : {e}", 500)

    client_form = _map_client_to_form(raw["client"])
    payload = {
        "client": client_form,
        "signataires": [_map_signataire(r) for r in raw["signataires"]],
        "dirigeants": [_map_signataire(r) for r in raw["dirigeants"]],
        "actionnaires": [_map_actionnaire(r) for r in raw["actionnaires"]],
        "infos_fin": [_map_infos_fin(r) for r in raw["infos_fin"]],
        "pour_compte_de": client_form.get("raison_sociale", ""),
        "fait_a": "",
        "le": "",
        "date_jour": datetime.date.today().strftime("%d/%m/%Y"),
    }

    try:
        pdf_bytes = generate_kyc_pdf(payload)
    except Exception as e:
        return _kyc_error_page(f"Erreur de génération du PDF : {e}", 500)

    return Response(
        pdf_bytes,
        mimetype="application/pdf",
        headers={"Content-Disposition": f"inline; filename=fiche_kyc_{matricule}.pdf"},
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 4444))
    # debug=False : ce process ne doit pas être utilisé tel quel en production,
    # préférer Gunicorn (voir README / service systemd).
    app.run(debug=False, host="0.0.0.0", port=port)
