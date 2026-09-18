"""
FORMA — Plateforme de génération de documents UM-ACEP.

Dev local :   python app.py
Production :  gunicorn -w 3 -b 0.0.0.0:4444 app:app
"""
import datetime
import os
import time

from flask import Flask, render_template, request, jsonify, Response, session, redirect
from doc_engine import DOC_TYPES, generate_preview_html
from kyc_render import render_kyc_html, generate_kyc_pdf

app = Flask(__name__)
# Nécessaire pour signer le cookie de session utilisé par le lien
# /kyc-morale/<matricule> (voir plus bas). Valeur par défaut générée
# aléatoirement ; peut être surchargée via FLASK_SECRET_KEY sur le serveur.
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "83BfICCzQKxJ3DWro3_pJEc2lIBWDi8a3mvbWWO5Ksg")


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


@app.route("/kyc/token", methods=["POST"])
def kyc_mint_token():
    """
    Endpoint serveur-à-serveur (jamais appelé depuis le navigateur de
    l'utilisateur final) : le backend de l'appli appelante demande ici un
    jeton signé et à courte durée de vie pour un matricule donné, protégé par
    une clé API partagée (en-tête X-API-Key). L'appli appelante affiche
    ensuite à son utilisateur le lien /kyc/pdf/<token> renvoyé — jamais le
    matricule en clair.
    """
    from kyc_token import mint_kyc_token, check_api_key

    if not check_api_key(request.headers.get("X-API-Key")):
        return jsonify({"error": "Clé API invalide ou manquante (en-tête X-API-Key)."}), 401

    payload = request.get_json(force=True) or {}
    matricule = (payload.get("matricule") or "").strip()
    if not matricule:
        return jsonify({"error": "Merci de préciser un matricule."}), 400

    ttl_seconds = payload.get("ttl_seconds", 300)
    token = mint_kyc_token(matricule, ttl_seconds=ttl_seconds)
    return jsonify({"token": token, "path": f"/kyc/pdf/{token}", "expires_in": ttl_seconds})


def _kyc_pdf_response_for_matricule(matricule):
    """Logique commune : matricule -> lookup Oracle -> PDF (ou page d'erreur)."""
    from kyc_data import get_kyc_data, ClientIntrouvable, ClientPersonnePhysique

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


@app.route("/kyc/pdf/<token>", methods=["GET"])
def kyc_pdf_by_token(token):
    """
    Lien à jeton (le plus sûr) : GET /kyc/pdf/<token>. Le <token> n'est PAS
    le matricule (voir kyc_token.py) — il est vérifié puis décodé pour
    retrouver le matricule, ce qui empêche un utilisateur de modifier le lien
    pour consulter la fiche d'un autre client, et il expire tout seul.
    """
    from kyc_token import verify_kyc_token

    try:
        matricule = verify_kyc_token(token)
    except ValueError as e:
        return _kyc_error_page(str(e), 403)

    return _kyc_pdf_response_for_matricule(matricule)


@app.route("/kyc/pdf-direct/<matricule>", methods=["GET"])
def kyc_pdf_direct(matricule):
    """
    Lien à appeler côté appelant (ex: PL/SQL Oracle, simple concaténation de
    chaîne) : GET /kyc/pdf-direct/<matricule>?key=<clé>. Ce n'est pas cette
    URL que l'utilisateur final garde sous les yeux : une fois la clé
    vérifiée, on l'autorise pour quelques secondes (cookie de session signé,
    pas de matricule/clé dedans) puis on le redirige vers l'URL "propre"
    /kyc-morale/<matricule>, qui sert réellement le PDF. C'est cette 2e URL,
    sans clé visible, que le navigateur affiche.
    """
    from kyc_token import check_api_key

    if not check_api_key(request.args.get("key")):
        return _kyc_error_page("Clé invalide ou manquante (paramètre ?key=...).", 401)

    matricule = (matricule or "").strip()
    if not matricule:
        return _kyc_error_page("Merci de préciser un matricule dans le lien.", 400)

    session["kyc_pending"] = {"matricule": matricule, "exp": time.time() + 30}
    return redirect(f"/kyc-morale/{matricule}")


@app.route("/kyc-morale/<matricule>", methods=["GET"])
def kyc_morale_clean_url(matricule):
    """
    URL "propre" affichée au navigateur (sans clé) : accessible uniquement
    juste après un passage validé par /kyc/pdf-direct (autorisation à usage
    unique, valable 30 secondes, portée par un cookie de session signé — pas
    par le matricule/la clé). Visitée directement sans être passé par
    /kyc/pdf-direct au préalable, elle refuse l'accès.
    """
    matricule = (matricule or "").strip()
    pending = session.pop("kyc_pending", None)
    if not pending or pending.get("matricule") != matricule or pending.get("exp", 0) < time.time():
        return _kyc_error_page(
            "Accès direct non autorisé. Merci d'ouvrir la fiche depuis l'application d'origine.",
            403,
        )
    return _kyc_pdf_response_for_matricule(matricule)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 4444))
    # debug=False : ce process ne doit pas être utilisé tel quel en production,
    # préférer Gunicorn (voir README / service systemd).
    app.run(debug=False, host="0.0.0.0", port=port)
