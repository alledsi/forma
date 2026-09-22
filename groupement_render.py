"""
Rendu HTML/PDF de la fiche KYC groupement — même moteur visuel que
kyc_render.py (fiche personne morale) : couleurs ACEP, tableaux bordés,
en-tête + pagination répétés sur chaque page PDF.

Les briques bas niveau (couleurs, échappement HTML, tableau bloc "label /
valeur", tableau dynamique, enveloppe PDF avec en-tête/pied de page) sont
réutilisées depuis kyc_render.py pour garder un rendu strictement identique
entre les deux fiches.
"""
from kyc_render import (
    GREEN,
    _e,
    _cell,
    _bloc1_table,
    _dynamic_table,
    _label_oui_non,
    _label_statut_client,
    wrap_pdf_document,
    GOUVERNANCE_COLS,
)

TYPE_ECOLE_LABELS = {
    "1": "Préscolaire",
    "2": "Secondaire",
    "3": "Enseignement supérieur",
    "4": "Enseignement technique et professionnel",
    "5": "Elémentaire",
}

SITUATION_HABITATION_LABELS = {
    "L": "Location",
    "P": "Pleine propriété",
    "C": "Copropriété",
    "F": "Partagé (avec la famille)",
}

# Pas de jointure Oracle pour ces deux-là : correspondances fixes fournies
# directement, en dur.
PREFIXE_LABELS = {
    "4": "Groupement",
}

TYPE_PIECE_LABELS = {
    "C": "Carte Nationale d'identité",
    "P": "Passeport CDEAO",
}


def _label_type_ecole(v):
    v = (v or "").strip()
    if v.upper() == "N":
        return ""
    return TYPE_ECOLE_LABELS.get(v, v)


def _label_situation_habitation(v):
    v = (v or "").strip().upper()
    return SITUATION_HABITATION_LABELS.get(v, v)


def _label_prefixe(v):
    v = (v or "").strip()
    return PREFIXE_LABELS.get(v, v)


def _label_type_piece(v):
    v = (v or "").strip().upper()
    return TYPE_PIECE_LABELS.get(v, v)


# --- Bloc 1 : identification client (19 lignes, paires gauche/droite) -----
BLOC1_PAIRS_GROUPEMENT = [
    ("matricule_client", "Matricule Client", "code_bureau", "Bureau"),
    ("localite", "Localité", "prefixe_client", "Préfixe"),
    ("prenom_client", "Prénom", "statut_client", "Statut client"),
    ("raison_sociale_client", "Nom ou raison sociale", "date_creation_client", "Date création client"),
    ("lieu_naissance", "Lieu de naissance", "date_naissance_entrepreneur", "Date naissance entrepreneur"),
    ("type_piece", "Type pièce d'identité", "numero_piece_identite", "Numéro pièce Identité"),
    ("lieu_delivrance_piece", "Lieu délivrance pièce", "date_delivrance_piece", "Date délivrance pièce"),
    ("date_expiration_piece", "Date d'expiration pièce", "nationalite", "Nationalité"),
    ("email", "Email client", "telephone", "Téléphone"),
    ("portable2", "Portable 2", "portable3", "Portable 3"),
    ("telephone_domicile", "Téléphone domicile", "whatsapp", "N° WhatsApp"),
    ("prenom_pere", "Prénom père", "prenom_mere", "Prénom mère"),
    ("nom_mere", "Nom mère", "situation_habitation", "Situation habitation"),
    ("sms_connect", "Sms Connect", "consentement", "Consentement ?"),
    ("numero_consentement", "Numéro Consentement", "employeur", "Employeur"),
    ("code_cotation", "Code cotation", "profession", "Profession"),
    ("nature", "Nature", "code_categorie", "Code catégorie"),
    ("gestionnaire", "Gestionnaire affecté", "type_ecole", "Type d'école"),
    ("adresse_entrepreneur", "Adresse entrepreneur", "", ""),
]

# --- Activités : liste simple label / valeur (pas de paires gauche/droite,
# faute d'une disposition à 2 colonnes cohérente côté source) ---------------
ACTIVITES_ITEMS = [
    ("raison_sociale_activite", "Raison sociale"),
    ("date_creation_entreprise", "Date création entreprise"),
    ("activite_principale", "Activité principale"),
    ("activite_secondaire", "Activité secondaire"),
    ("revenu_mensuel", "Revenu mensuel"),
    ("origine_revenu", "Origine revenu"),
    ("no_registre_commerce", "N° registre commerce"),
    ("ninea", "NINEA"),
    ("adresse_entreprise", "Adresse entreprise"),
    ("sous_secteur_activite", "Sous-secteur"),
    ("secteur_activite", "Secteur"),
    ("tel_entreprise_fixe", "Téléphone entreprise (Fixe)"),
    ("tel_entreprise_portable", "Téléphone entreprise (Portable)"),
    ("contrat_travail", "Contrat de travail"),
    ("tel_portable_bureau", "Téléphone portable (bureau)"),
    ("tel_fixe_bureau", "Téléphone fixe (bureau)"),
    ("date_titularisation", "Date de titularisation"),
]

PPE_PAIRS = [
    ("client_ppe", "Client PPE ?", "fonction_ppe", "Fonction"),
    ("pays_fonction_ppe", "Pays", "date_debut_fonction", "Date d'entrée en fonction"),
    ("date_fin_fonction", "Date fin fonction", "", ""),
]
FAMILLE_PPE_PAIRS = [
    ("prenom_par_ppe", "Prénom", "nom_par_ppe", "Nom"),
    ("lien_parente", "Lien parenté", "fonction_par_ppe", "Fonction"),
    ("pays_par_ppe", "Pays", "", ""),
]

CONJOINT_COLS = [
    ("prenom", "Prénom"), ("nom", "Nom"), ("profession", "Profession"), ("telephone", "Téléphone"),
]
ENFANT_COLS = [
    ("prenom", "Prénom"), ("nom", "Nom"), ("numero_identite", "N° pièce d'identité"),
    ("telephone", "Téléphone"), ("email", "Email"),
]
# "Membre" fusionne dirigeants + signataires : mêmes colonnes que la fiche
# personne morale (Signataire / Dirigeant), réutilisées telles quelles.
MEMBRE_COLS = GOUVERNANCE_COLS

DECLARATION_1 = (
    "Je soussigné(e), agissant en qualité de gérant du groupement dénommé {nom_groupement}, "
    "déclare que ledit groupement est le titulaire du compte ouvert dans vos livres et que "
    "les bénéficiaires effectifs des transactions qui y seront effectuées sont les membres "
    "dudit groupement, dûment identifiés dans la présente fiche."
)
DECLARATION_2 = (
    "Je déclare et garantis que les documents remis à l'institution ACEP, ainsi que "
    "les informations communiquées à cette dernière lors de l'ouverture du compte et "
    "pendant toute la durée de la relation, sont exacts, réguliers et sincères."
)
DECLARATION_3 = (
    "Je m'engage, par ailleurs, à informer l'ACEP de toute modification de la situation "
    "du groupement au plus tard dans les 30 jours suivant le changement."
)


def _prepare_client_display(client):
    """Copie du client avec les codes traduits en libellés lisibles pour l'affichage."""
    c = dict(client or {})
    c["sms_connect"] = _label_oui_non(c.get("sms_connect"))
    c["consentement"] = _label_oui_non(c.get("consentement"))
    c["client_ppe"] = _label_oui_non(c.get("client_ppe"))
    c["statut_client"] = _label_statut_client(c.get("statut_client"))
    c["type_ecole"] = _label_type_ecole(c.get("type_ecole"))
    c["situation_habitation"] = _label_situation_habitation(c.get("situation_habitation"))
    c["prefixe_client"] = _label_prefixe(c.get("prefixe_client"))
    c["type_piece"] = _label_type_piece(c.get("type_piece"))
    return c


def _single_col_table(items, data):
    """Tableau label/valeur en une seule colonne (une ligne = un champ),
    même habillage visuel (bordures, couleurs) que _bloc1_table."""
    from kyc_render import BORDER, OUTER_BORDER

    rows = []
    for key, label in items:
        rows.append(
            "<tr>"
            f'<td style="border:1px solid {BORDER};padding:7px 12px;font-weight:bold;'
            f'width:30%;background:#F2F6F4;">{_e(label)}</td>'
            f'<td style="border:1px solid {BORDER};padding:7px 12px;">{_cell(data.get(key))}</td>'
            "</tr>"
        )
    inner = (
        '<table style="border-collapse:collapse;width:100%;font-size:10.5pt;'
        f'font-family:Arial, sans-serif;">{"".join(rows)}</table>'
    )
    return f'<div style="border:1.5px solid {OUTER_BORDER};margin:10px 0 24px;overflow:hidden;">{inner}</div>'


def render_groupement_html(data, include_date_line=True):
    """
    data = {
        'date_jour': str, 'client': {...}, 'conjoints': [...], 'enfants': [...],
        'membres': [...], 'fait_a': str, 'le': str,
    }
    """
    client = _prepare_client_display(data.get("client", {}))
    date_jour = _e(data.get("date_jour", ""))
    fait_a = _e(data.get("fait_a", ""))
    le = _e(data.get("le", ""))
    nom_groupement = _e(client.get("raison_sociale_client") or "……………………………………………………")

    parts = []
    if include_date_line:
        parts.append(
            f'<p style="text-align:right;margin:0;font-size:9pt;'
            f'font-family:Arial, sans-serif;">Date : {date_jour or "____ / ____ / ________"}</p>'
        )
    parts.append(
        '<p style="text-align:center;margin:26px 0 0;font-size:16pt;font-weight:bold;'
        'font-family:Arial, sans-serif;">FICHE KYC GROUPEMENT</p>'
    )
    parts.append(f'<div style="width:100%;height:3px;background:{GREEN};margin:10px 0 28px;"></div>')

    parts.append(
        '<h2 style="font-size:13pt;margin:0 0 6px;font-family:Arial, sans-serif;">1. Client</h2>'
    )
    parts.append(_bloc1_table(client, BLOC1_PAIRS_GROUPEMENT))

    parts.append(
        '<h2 style="font-size:13pt;margin:20px 0 6px;font-family:Arial, sans-serif;">2. Conjoints / Enfants</h2>'
    )
    parts.append(_dynamic_table("Conjoint(e)s", CONJOINT_COLS, data.get("conjoints", [])))
    parts.append(_dynamic_table("Enfants", ENFANT_COLS, data.get("enfants", [])))

    parts.append(
        '<h2 style="font-size:13pt;margin:20px 0 6px;font-family:Arial, sans-serif;">3. Activités</h2>'
    )
    parts.append(_single_col_table(ACTIVITES_ITEMS, client))

    parts.append(
        '<h2 style="font-size:13pt;margin:20px 0 6px;font-family:Arial, sans-serif;">'
        '4. PPE (Personne Politiquement Exposée)</h2>'
    )
    parts.append(
        '<h3 style="font-size:11.5pt;margin:0 0 6px;font-family:Arial, sans-serif;'
        f'color:{GREEN};">Personne politiquement exposée</h3>'
    )
    parts.append(_bloc1_table(client, PPE_PAIRS))
    parts.append(
        '<h3 style="font-size:11.5pt;margin:0 0 6px;font-family:Arial, sans-serif;'
        f'color:{GREEN};">Personne de la famille</h3>'
    )
    parts.append(_bloc1_table(client, FAMILLE_PPE_PAIRS))

    parts.append(
        '<h2 style="font-size:13pt;margin:20px 0 6px;font-family:Arial, sans-serif;">'
        '5. Dirigeants et signataires autorisés</h2>'
    )
    parts.append(_dynamic_table("Membre", MEMBRE_COLS, data.get("membres", [])))

    parts.append(
        f'<p style="text-align:right;margin:24px 0 20px;font-size:10.5pt;font-family:Arial, sans-serif;">'
        f'Fait à {fait_a or "____________________________"}'
        f'&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Le {le or "____________________________"}</p>'
    )

    decl_style = 'style="margin:8px 0;font-size:10.5pt;font-family:Arial, sans-serif;text-align:justify;"'
    parts.append(f'<p {decl_style}>{DECLARATION_1.format(nom_groupement=nom_groupement)}</p>')
    parts.append(f'<p {decl_style}>{DECLARATION_2}</p>')
    parts.append(f'<p {decl_style}>{DECLARATION_3}</p>')

    parts.append(
        '<div style="display:flex;justify-content:space-between;align-items:baseline;'
        'margin-top:34px;font-size:10.5pt;font-family:Arial, sans-serif;">'
        '<span style="font-weight:bold;">Signature du gérant</span>'
        '<span style="font-weight:bold;">Signature ACEP</span>'
        '</div>'
    )
    parts.append(
        '<p style="margin:6px 0 0;font-size:9pt;color:#555;font-family:Arial, sans-serif;">'
        "(Précédée de la mention « je déclare sur honneur »)</p>"
    )

    return "".join(parts)


def render_groupement_pdf_html(data):
    body = render_groupement_html(data, include_date_line=False)
    date_jour = _e(data.get("date_jour", ""))
    return wrap_pdf_document(body, date_jour, title="Fiche KYC Groupement")


def generate_groupement_pdf(data):
    """Retourne les octets du PDF de la fiche KYC groupement (en-tête logo +
    ACEP et numérotation de pages, identique à la fiche personne morale)."""
    from weasyprint import HTML
    import os

    html_doc = render_groupement_pdf_html(data)
    return HTML(string=html_doc, base_url=os.path.dirname(__file__)).write_pdf()
