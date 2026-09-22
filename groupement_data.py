"""
Requêtes Oracle ACE pour la fiche KYC groupement.

Même logique que kyc_data.py (personne morale) : toutes les colonnes des
tables enfants (CONJOINT_CLIENT, ENFANT_CLIENT, DIRIGEANT, SIGNATAIRE) sont
NULLABLE, on neutralise systématiquement les valeurs manquantes.

Contrairement à la personne morale (où PREFIXE_CLIENT = '0' est directement
comparé), le "groupement" est identifié via son libellé dans la table de
référence PREFIXE_CLIENT (LIB_PREFIXE), car aucun code numérique fixe n'a été
communiqué — plus robuste si les codes venaient à changer.
"""
import datetime
import decimal

from db import fetch_all, fetch_one

SQL_CLIENT = """
SELECT
    c.MATRICULE_CLIENT, c.CODE_BUREAU, c.CODE_LOC, c.PREFIXE_CLIENT,
    c.PRENOM_CLIENT, c.RAISON_SOCIALE_CLIENT, c.STATUT_CLIENT, c.DATE_CRE,
    c.LIEU_NAISSANCE, c.DATE_NAISSANCE, c.DATE_NAISSANCE_ENTREPRENEUR,
    c.TYPE_PIECE, tp.LIBELLE_TYPE_PIECE, c.NUMERO_PIECE_IDENTITE,
    c.LIEU_DELIVRANCE_PIECE, c.DATE_DELIVRANCE_PIECE, c.DATE_EXPIRATION_PIECE,
    c.CODE_NATION, p.LIB_PAYS,
    c.EMAIL, c.TEL_PORT, c.TEL_PORT2, c.TEL_PORT3, c.TEL_DOM, c.NO_WHATSAPP,
    c.NOM_PERE, c.PRENOM_MERE, c.NOM_MERE, c.SITUATION_HABITATION,
    c.SMS_CONNECT, c.CONSENTEMENT, c.NO_CONSENT,
    c.ID_EMPLOYEUR, c.CODE_COTATION, co.LIB_COTATION,
    c.CODE_PROF, prof.LIB_PROF, c.CODE_NATURE, nc.LIB_NATURE,
    c.CODE_CATEGORIE, cat.INT_CATEGORIE,
    c.CODE_GESTIONNAIRE, g.NOM_GESTIONNAIRE, c.TYPE_ECOLE,
    c.ADRESSE_1, c.ADRESSE_2,
    c.RAISON_SOCIALE, c.ACTIVITE_PRINCIPALE, c.ACTIVITE_SECONDAIRE,
    c.REVENU_MENSUEL, c.ORIGINE_REVENU,
    c.NO_REGISTRE_COMMERCE, c.NINEA,
    c.CODE_SSECT, ss.LIB_SSECT, se.LIB_SECT,
    c.TEL_ENTREPRISE_FIXE, c.TEL_ENTREPRISE_PORTABLE,
    c.CONTRAT_TRAVAIL, tc.INTITULE_TYPE_CONTRAT, c.TEL_FIXE_BUREAU, c.TEL_PORT_BUREAU,
    c.DATE_TITULARISATION,
    c.NB_CONJOINTS,
    c.CLIENT_PPE, c.FONCTION_PPE, c.PAYS_FONCTION_PPE,
    c.DATE_DEBUT_FONCTION, c.DATE_FIN_FONCTION,
    c.PRENOM_PAR_PPE, c.NOM_PAR_PPE, c.LIEN_PARENTE,
    c.FONCTION_PAR_PPE, c.PAYS_PAR_PPE,
    pc.LIB_PREFIXE, loc.LIB_LOC
FROM CLIENT c
LEFT JOIN PREFIXE_CLIENT pc ON pc.CODE_PREFIXE = c.PREFIXE_CLIENT
LEFT JOIN LOCALITE loc ON loc.CODE_LOC = c.CODE_LOC AND loc.CODE_BUREAU = c.CODE_BUREAU
LEFT JOIN SOUS_SECTEUR ss ON ss.CODE_SSECT = c.CODE_SSECT
LEFT JOIN SECTEUR se ON se.CODE_SECT = ss.CODE_SECT
LEFT JOIN PAYS p ON p.CODE_PAYS = c.CODE_NATION
LEFT JOIN COTATION co ON co.CODE_COTATION = c.CODE_COTATION
LEFT JOIN NAT_CLIENT nc ON nc.CODE_NATURE = c.CODE_NATURE
LEFT JOIN CATEGORIE cat ON cat.CODE_CATEGORIE = c.CODE_CATEGORIE
LEFT JOIN GESTIONNAIRE g ON g.CODE_GESTIONNAIRE = c.CODE_GESTIONNAIRE
LEFT JOIN TYPE_PIECE tp ON tp.CODE_TYPE_PIECE = c.TYPE_PIECE
LEFT JOIN PROFESSION prof ON prof.CODE_PROF = c.CODE_PROF
LEFT JOIN TYPE_CONTRAT tc ON tc.CODE_TYPE_CONTRAT = c.CONTRAT_TRAVAIL
WHERE c.MATRICULE_CLIENT = :matricule
"""

SQL_CONJOINT = """
SELECT PRENOM, NOM, PROFESSION, TELEPHONE
FROM CONJOINT_CLIENT
WHERE MATRICULE_CLIENT = :matricule
"""

SQL_ENFANT = """
SELECT PRENOM, NOM, TYPE_IDENTITE, NUMERO_IDENTITE, DATE_NAISSANCE, TELEPHONE, EMAIL
FROM ENFANT_CLIENT
WHERE MATRICULE_CLIENT = :matricule
"""

# "Membre" (section 5 du Word) fusionne dirigeants et signataires dans une
# seule liste, comme demandé — même structure de colonnes pour les deux.
SQL_DIRIGEANT = """
SELECT d.PRENOM, d.NOM, d.FONCTIONS, d.NUMERO_PIECE_IDENTITE, p.LIB_PAYS AS NATIONALITE
FROM DIRIGEANT d
LEFT JOIN PAYS p ON p.CODE_PAYS = d.CODE_PAYS
WHERE d.MATRICULE_CLIENT = :matricule
"""

SQL_SIGNATAIRE = """
SELECT s.PRENOM, s.NOM, s.FONCTIONS, s.NUMERO_PIECE_IDENTITE, p.LIB_PAYS AS NATIONALITE
FROM SIGNATAIRE s
LEFT JOIN PAYS p ON p.CODE_PAYS = s.CODE_PAYS
WHERE s.MATRICULE_CLIENT = :matricule
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


def get_groupement_data(matricule):
    """
    Retourne les données KYC groupement complètes pour un matricule donné :
    {client: {...}, conjoints: [...], enfants: [...], membres: [...]}

    Lève ClientIntrouvable si le matricule n'existe pas. Aucune vérification
    du type de client (préfixe) n'est faite ici : on affiche les infos pour
    n'importe quel matricule fourni.
    """
    matricule = (matricule or "").strip()
    client = fetch_one(SQL_CLIENT, {"matricule": matricule})
    if client is None:
        raise ClientIntrouvable(f"Aucun client trouvé pour le matricule {matricule}.")

    membres = fetch_all(SQL_DIRIGEANT, {"matricule": matricule}) + fetch_all(
        SQL_SIGNATAIRE, {"matricule": matricule}
    )

    return {
        "client": _clean_row(client),
        "conjoints": _clean_rows(fetch_all(SQL_CONJOINT, {"matricule": matricule})),
        "enfants": _clean_rows(fetch_all(SQL_ENFANT, {"matricule": matricule})),
        "membres": _clean_rows(membres),
    }
