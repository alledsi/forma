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
from kyc_render import render_kyc_html, generate_kyc_pdf, GREEN

app = Flask(__name__)

# --- Réglages temporaires -----------------------------------------------
# Le temps de faire monter la fiche KYC en priorité, on masque les 4
# attestations du menu (le code reste intact, il suffit de repasser ce
# drapeau à True pour tout réafficher) et on protège l'entrée dans
# l'application par un code fixe.
SHOW_ATTESTATIONS = False
ACCESS_CODE = os.environ.get("FORMA_ACCESS_CODE", "1319")
# --------------------------------------------------------------------------
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


def require_login(view):
    """
    Protège les endpoints de l'appli FORMA elle-même (utilisés par l'écran
    de connexion par code) — n'a aucun effet sur /kyc/pdf-direct,
    /kyc-morale et /kyc/token, qui ont leur propre protection par clé/jeton
    et sont appelés par d'autres applis, pas par un utilisateur connecté ici.
    """
    from functools import wraps

    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("forma_authed"):
            return jsonify({"error": "Merci de vous reconnecter (code d'accès)."}), 401
        return view(*args, **kwargs)

    return wrapped


@app.route("/login", methods=["POST"])
def login():
    payload = request.get_json(force=True) or {}
    code = str(payload.get("code") or "").strip()
    if code != ACCESS_CODE:
        return jsonify({"error": "Code incorrect."}), 401
    session["forma_authed"] = True
    return jsonify({"ok": True})


@app.route("/")
def index():
    # Le code d'accès est redemandé à chaque chargement de page (F5, nouvel
    # onglet, etc.) plutôt que mémorisé : plus sûr, quitte à le retaper à
    # chaque fois. On invalide donc la session ici, systématiquement.
    session.pop("forma_authed", None)

    # On n'envoie au front que ce qui est nécessaire (pas row_map/date_in_label_row)
    doc_types_public = {}
    if SHOW_ATTESTATIONS:
        doc_types_public = {
            key: {
                "label": cfg["label"],
                "description": cfg.get("description", ""),
                "icon": cfg.get("icon", "📄"),
                "fields": cfg["fields"],
            }
            for key, cfg in DOC_TYPES.items()
        }
    return render_template("index.html", doc_types=doc_types_public, authed=False)


@app.route("/preview", methods=["POST"])
@require_login
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
@require_login
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
@require_login
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
@require_login
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


def _kyc_loading_page(matricule):
    """
    Page affichée instantanément (avant même d'aller chercher quoi que ce
    soit dans Oracle) : un spinner, pendant que le PDF est généré en
    arrière-plan via un appel JS (?fetchpdf=1) sur cette même URL, puis
    affiché dans la page une fois prêt — sans jamais changer l'adresse
    affichée dans le navigateur.
    """
    html_page = f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>Fiche KYC</title>
<style>
  html, body {{ height:100%; margin:0; }}
  body {{
    font-family: Arial, sans-serif;
    display:flex; flex-direction:column; align-items:center; justify-content:center;
    background:#fafafa; color:#333;
  }}
  .spinner {{
    width:40px; height:40px; border:4px solid #dcdcdc; border-top-color:{GREEN};
    border-radius:50%; animation:spin 0.8s linear infinite; margin-bottom:16px;
  }}
  @keyframes spin {{ to {{ transform: rotate(360deg); }} }}
  #msg {{ font-size:14px; color:#555; }}
  #err {{ display:none; color:#b00020; text-align:center; padding:0 24px; font-size:14px; }}
  iframe {{ position:fixed; inset:0; width:100%; height:100%; border:none; display:none; }}
</style>
</head>
<body>
  <div id="loading">
    <div class="spinner"></div>
    <div id="msg">Génération de la fiche KYC en cours…</div>
  </div>
  <div id="err"></div>
  <iframe id="pdfFrame" title="Fiche KYC"></iframe>
  <script>
    fetch(window.location.pathname + '?fetchpdf=1')
      .then(function (res) {{
        if (!res.ok) {{ throw new Error('HTTP ' + res.status); }}
        return res.blob();
      }})
      .then(function (blob) {{
        var url = URL.createObjectURL(blob);
        document.getElementById('loading').style.display = 'none';
        var frame = document.getElementById('pdfFrame');
        frame.src = url;
        frame.style.display = 'block';
      }})
      .catch(function () {{
        document.getElementById('loading').style.display = 'none';
        var err = document.getElementById('err');
        err.textContent = "Impossible de charger la fiche KYC (lien expiré ou déjà utilisé). Merci de réessayer depuis l'application d'origine.";
        err.style.display = 'block';
      }});
  </script>
</body>
</html>"""
    return Response(html_page, mimetype="text/html")


@app.route("/kyc-morale/<matricule>", methods=["GET"])
def kyc_morale_clean_url(matricule):
    """
    URL "propre" affichée au navigateur (sans clé) : accessible uniquement
    juste après un passage validé par /kyc/pdf-direct (autorisation à usage
    unique, valable 30 secondes, portée par un cookie de session signé — pas
    par le matricule/la clé). Visitée directement sans être passé par
    /kyc/pdf-direct au préalable, elle refuse l'accès.

    En deux temps pour permettre un affichage de chargement : le premier
    chargement (sans ?fetchpdf) renvoie instantanément une page avec spinner,
    qui va elle-même chercher le PDF en arrière-plan (étape lente : requête
    Oracle + génération WeasyPrint) sans jamais changer l'URL affichée.
    """
    matricule = (matricule or "").strip()
    pending = session.get("kyc_pending")
    valid = bool(pending) and pending.get("matricule") == matricule and pending.get("exp", 0) > time.time()

    if request.args.get("fetchpdf"):
        session.pop("kyc_pending", None)  # à usage unique : consommé ici, à l'étape qui sert vraiment le PDF
        if not valid:
            return _kyc_error_page(
                "Accès direct non autorisé ou expiré. Merci d'ouvrir la fiche depuis l'application d'origine.",
                403,
            )
        return _kyc_pdf_response_for_matricule(matricule)

    if not valid:
        return _kyc_error_page(
            "Accès direct non autorisé. Merci d'ouvrir la fiche depuis l'application d'origine.",
            403,
        )
    return _kyc_loading_page(matricule)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 4444))
    # debug=False : ce process ne doit pas être utilisé tel quel en production,
    # préférer Gunicorn (voir README / service systemd).
    app.run(debug=False, host="0.0.0.0", port=port)
