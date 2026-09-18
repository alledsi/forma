"""
FORMA — Plateforme de génération de documents UM-ACEP.

Dev local :   python app.py
Production :  gunicorn -w 3 -b 0.0.0.0:4444 app:app
"""
import datetime
import os

from flask import Flask, render_template, request, jsonify
from doc_engine import DOC_TYPES, generate_preview_html
from kyc_render import render_kyc_html

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
        "forme_juridique": client.get("CODE_FORME", ""),
        "agrement": "",
        "no_agrement": client.get("NO_AGREMENT", ""),
        "delivre_par": client.get("DELIVRE_PAR", ""),
        "no_registre_commerce": client.get("NO_REGISTRE_COMMERCE", ""),
        "date_deliv_registre": client.get("DATE_DELIV_RC", ""),
        "ninea": client.get("NINEA", ""),
        "date_deliv_ninea": client.get("DATE_DELIV_NINEA", ""),
        "code_sous_secteur": client.get("CODE_SSECT", ""),
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


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 4444))
    # debug=False : ce process ne doit pas être utilisé tel quel en production,
    # préférer Gunicorn (voir README / service systemd).
    app.run(debug=False, host="0.0.0.0", port=port)
