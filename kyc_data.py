"""
Requêtes Oracle ACE pour la fiche KYC personne morale.

Toutes les colonnes des tables SIGNATAIRE, DIRIGEANT, ACTIONNAIRE, INFOS_FIN
sont NULLABLE : on neutralise systématiquement les valeurs manquantes (None
-> chaîne vide) plutôt que de laisser une erreur remonter à l'écran.
"""
import datetime
import decimal

from db import fetch_all, fetch_one

SQL_CLIENT = """
SELECT
    c.MATRICULE_CLIENT, c.CODE_BUREAU, c.RAISON_SOCIALE_CLIENT, c.STATUT_CLIENT,
    c.SIGLE_CLIENT, c.DATE_CRE, c.CODE_FORME, c.NO_AGREMENT, c.DELIVRE_PAR,
    c.NO_REGISTRE_COMMERCE, c.DATE_DELIV_RC, c.NINEA, c.DATE_DELIV_NINEA,
    c.CODE_SSECT, ss.LIB_SSECT, se.LIB_SECT,
    c.TEL_ENTREPRISE_FIXE, c.EMAIL, c.ADRESSE_1, c.ADRESSE_2, c.ADRESSE_POST,
    c.CODE_NATION, p.LIB_PAYS,
    c.CODE_COTATION, co.LIB_COTATION,
    c.CODE_NATURE, nc.LIB_NATURE,
    c.CODE_CATEGORIE, cat.INT_CATEGORIE,
    c.CODE_GESTIONNAIRE, g.NOM_GESTIONNAIRE,
    c.SMS_CONNECT, c.CONSENTEMENT, c.NO_CONSENT, c.PREFIXE_CLIENT,
    fj.LIBELLE_FORME
FROM CLIENT c
LEFT JOIN SOUS_SECTEUR ss ON ss.CODE_SSECT = c.CODE_SSECT
LEFT JOIN SECTEUR se ON se.CODE_SECT = ss.CODE_SECT
LEFT JOIN PAYS p ON p.CODE_PAYS = c.CODE_NATION
LEFT JOIN COTATION co ON co.CODE_COTATION = c.CODE_COTATION
LEFT JOIN NAT_CLIENT nc ON nc.CODE_NATURE = c.CODE_NATURE
LEFT JOIN CATEGORIE cat ON cat.CODE_CATEGORIE = c.CODE_CATEGORIE
LEFT JOIN GESTIONNAIRE g ON g.CODE_GESTIONNAIRE = c.CODE_GESTIONNAIRE
LEFT JOIN FORME_JURIDIQUE fj ON fj.CODE_FORME = c.CODE_FORME
WHERE c.MATRICULE_CLIENT = :matricule
"""

SQL_SIGNATAIRE = """
SELECT s.PRENOM, s.NOM, s.FONCTIONS, s.NUMERO_PIECE_IDENTITE, p.LIB_PAYS AS NATIONALITE
FROM SIGNATAIRE s
LEFT JOIN PAYS p ON p.CODE_PAYS = s.CODE_PAYS
WHERE s.MATRICULE_CLIENT = :matricule
"""

SQL_DIRIGEANT = """
SELECT d.PRENOM, d.NOM, d.FONCTIONS, d.NUMERO_PIECE_IDENTITE, p.LIB_PAYS AS NATIONALITE
FROM DIRIGEANT d
LEFT JOIN PAYS p ON p.CODE_PAYS = d.CODE_PAYS
WHERE d.MATRICULE_CLIENT = :matricule
"""

SQL_ACTIONNAIRE = """
SELECT a.PRENOM, a.NOM, a.NUMERO_PIECE_IDENTITE, a.PART, p.LIB_PAYS AS NATIONALITE
FROM ACTIONNAIRE a
LEFT JOIN PAYS p ON p.CODE_PAYS = a.CODE_PAYS
WHERE a.MATRICULE_CLIENT = :matricule
"""

SQL_INFOS_FIN = """
SELECT ANNEE, CHIFFRE_AFFAIRE, RESULTAT_NET, CAPITAL, EFFECTIF
FROM INFOS_FIN
WHERE MATRICULE_CLIENT = :matricule
ORDER BY ANNEE DESC
"""


def _clean_value(v):
    """None -> '' ; dates -> JJ/MM/AAAA ; Decimal -> str (pour affichage/édition)."""
    if v is None:
        return ""
    if isinstance(v, (datetime.date, datetime.datetime)):
        return v.strftime("%d/%m/%Y")
    if isinstance(v, decimal.Decimal):
        return str(v)
    return v


def _clean_row(row):
    return {k: _clean_value(v) for k, v in row.items()}


def _clean_rows(rows):
    return [_clean_row(r) for r in rows]


class ClientIntrouvable(Exception):
    pass


class ClientPersonnePhysique(Exception):
    pass


def get_kyc_data(matricule):
    """
    Retourne les données KYC complètes pour un matricule donné :
    {client: {...}, signataires: [...], dirigeants: [...],
     actionnaires: [...], infos_fin: [...]}

    Lève ClientIntrouvable si le matricule n'existe pas, ClientPersonnePhysique
    si ce n'est pas une personne morale (PREFIXE_CLIENT != '0').
    """
    matricule = (matricule or "").strip()
    client = fetch_one(SQL_CLIENT, {"matricule": matricule})
    if client is None:
        raise ClientIntrouvable(f"Aucun client trouvé pour le matricule {matricule}.")

    if str(client.get("PREFIXE_CLIENT") or "").strip() != "0":
        raise ClientPersonnePhysique(
            f"Le matricule {matricule} correspond à une personne physique, "
            "pas à une personne morale."
        )

    return {
        "client": _clean_row(client),
        "signataires": _clean_rows(fetch_all(SQL_SIGNATAIRE, {"matricule": matricule})),
        "dirigeants": _clean_rows(fetch_all(SQL_DIRIGEANT, {"matricule": matricule})),
        "actionnaires": _clean_rows(fetch_all(SQL_ACTIONNAIRE, {"matricule": matricule})),
        "infos_fin": _clean_rows(fetch_all(SQL_INFOS_FIN, {"matricule": matricule})),
    }
