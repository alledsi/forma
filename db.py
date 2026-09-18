"""
Connexion à la base Oracle ACE (core banking ACEP).

Valeurs par défaut de l'instance ACE (host 192.168.0.204, port 1539, SID
"ace", user "ace", mot de passe "ace"). Surchargeables via variables
d'environnement si besoin (utile si le mot de passe change un jour sans
retoucher le code) :

    ORACLE_HOST, ORACLE_PORT, ORACLE_SID, ORACLE_USER, ORACLE_PASSWORD
"""
import os
import oracledb

ORACLE_HOST = os.environ.get("ORACLE_HOST", "192.168.0.204")
ORACLE_PORT = int(os.environ.get("ORACLE_PORT", "1539"))
ORACLE_SID = os.environ.get("ORACLE_SID", "ace")
ORACLE_USER = os.environ.get("ORACLE_USER", "ace")
ORACLE_PASSWORD = os.environ.get("ORACLE_PASSWORD", "ace")

# Mode "thin" (pur Python, pas besoin d'Oracle Instant Client installé sur le serveur)
oracledb.defaults.fetch_lobs = False


def get_connection():
    if not all([ORACLE_HOST, ORACLE_SID, ORACLE_USER, ORACLE_PASSWORD]):
        raise RuntimeError(
            "Configuration Oracle incomplète : la variable d'environnement "
            "ORACLE_PASSWORD doit être définie sur le serveur (host/SID/user "
            "ont déjà une valeur par défaut)."
        )
    dsn = oracledb.makedsn(ORACLE_HOST, ORACLE_PORT, sid=ORACLE_SID)
    return oracledb.connect(user=ORACLE_USER, password=ORACLE_PASSWORD, dsn=dsn)


def fetch_all(sql, params=None):
    """Exécute une requête et retourne une liste de dicts {colonne: valeur}."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(sql, params or {})
        columns = [c[0] for c in cur.description]
        rows = cur.fetchall()
        return [dict(zip(columns, row)) for row in rows]
    finally:
        conn.close()


def fetch_one(sql, params=None):
    rows = fetch_all(sql, params)
    return rows[0] if rows else None
