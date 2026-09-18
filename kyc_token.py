"""
Jetons signés pour les liens directs "/kyc/pdf/<token>".

But : une autre application peut ouvrir directement le PDF d'une fiche KYC
dans le navigateur de son utilisateur, SANS exposer le matricule client en
clair dans l'URL (l'utilisateur pourrait sinon modifier le lien pour voir la
fiche d'un autre client).

Principe (identique aux "URL pré-signées" type S3) :
  - Le backend de l'appli appelante demande d'abord un jeton à FORMA
    (POST /kyc/token, protégé par une clé API partagée — appel serveur à
    serveur, jamais fait depuis le navigateur de l'utilisateur final).
  - Ce jeton encode le matricule + une date d'expiration courte, signés avec
    une clé secrète (HMAC-SHA256) que seul le serveur FORMA connaît.
  - Le lien affiché à l'utilisateur est /kyc/pdf/<token>. Impossible d'en
    déduire ou d'en fabriquer un autre sans la clé secrète, et il expire vite.

Aucun état à conserver côté serveur (important car FORMA tourne avec
plusieurs workers Gunicorn) : tout est vérifiable à partir du jeton lui-même.

IMPORTANT (sécurité) : TOKEN_SECRET et API_KEY ci-dessous ont des valeurs par
défaut générées aléatoirement (secrets.token_urlsafe), pas de simples
placeholders. Comme elles servent de contrôle d'accès réel (pas juste une
commodité comme le mot de passe Oracle sur le LAN), elles peuvent être
redéfinies via les variables d'environnement KYC_TOKEN_SECRET et
FORMA_API_KEY si besoin, mais ce n'est pas obligatoire. Ne communiquer
FORMA_API_KEY qu'à l'équipe qui gère le backend de l'appli appelante — c'est
la clé qui autorise à demander des jetons. Ces valeurs se retrouveront dans
l'historique Git une fois poussées : si le dépôt devient public un jour, il
faudra les régénérer.
"""
import base64
import hashlib
import hmac
import json
import os
import time

TOKEN_SECRET = os.environ.get("KYC_TOKEN_SECRET", "dGF_-zbgnhkwwbOGeQW82xjlYtJ-Aj8-DZfQA0dilec")
API_KEY = os.environ.get("FORMA_API_KEY", "GXuQTszjoD-BcaCI0ZYCe6BQ4dlSbAtkcvwjSZqZZCE")

MAX_TTL_SECONDS = 3600  # 1h max, pour éviter un jeton "éternel" par erreur


def _b64url_encode(raw_bytes):
    return base64.urlsafe_b64encode(raw_bytes).rstrip(b"=").decode("ascii")


def _b64url_decode(s):
    padded = s + "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(padded.encode("ascii"))


def _sign(body):
    sig = hmac.new(TOKEN_SECRET.encode("utf-8"), body.encode("ascii"), hashlib.sha256).digest()
    return _b64url_encode(sig)[:22]  # tronqué (~130 bits) : largement suffisant, lien plus court


def mint_kyc_token(matricule, ttl_seconds=300):
    """Génère un jeton signé encodant le matricule, valable ttl_seconds."""
    ttl_seconds = max(1, min(int(ttl_seconds), MAX_TTL_SECONDS))
    payload = {"m": str(matricule), "exp": int(time.time()) + ttl_seconds}
    body = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    return f"{body}.{_sign(body)}"


def verify_kyc_token(token):
    """Retourne le matricule si le jeton est valide et non expiré.
    Lève ValueError sinon (message adapté à un affichage utilisateur)."""
    if not token or "." not in token:
        raise ValueError("Lien invalide.")
    body, sig = token.rsplit(".", 1)
    if not hmac.compare_digest(sig, _sign(body)):
        raise ValueError("Lien invalide ou altéré.")
    try:
        payload = json.loads(_b64url_decode(body))
    except Exception:
        raise ValueError("Lien invalide.")
    matricule = payload.get("m")
    exp = payload.get("exp")
    if not matricule or not isinstance(exp, int):
        raise ValueError("Lien invalide.")
    if exp < time.time():
        raise ValueError("Ce lien a expiré. Merci de redemander la fiche depuis l'application d'origine.")
    return matricule


def check_api_key(candidate):
    """Comparaison à temps constant pour éviter les attaques par timing."""
    return hmac.compare_digest(candidate or "", API_KEY)
