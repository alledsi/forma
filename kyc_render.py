"""
Rendu HTML de la fiche KYC personne morale, dans le même style visuel que les
attestations FORMA (vert ACEP #02564A, tableaux bordés, titre souligné).

Contrairement aux attestations (template Word figé), cette fiche a des blocs
à nombre de lignes variable (signataires, dirigeants, bénéficiaires effectifs,
infos financières) : le rendu est donc construit dynamiquement en Python,
pas en remplissant un .docx existant.
"""
import html

GREEN = "#02564A"
BORDER = "#D9D9D9"
OUTER_BORDER = "#1F3864"

# (clé_champ, libellé) pour le Bloc 1, dans l'ordre d'affichage par paires
# gauche/droite, identique à la disposition du document Word source.
BLOC1_PAIRS = [
    ("matricule_client", "Matricule client", "code_bureau", "Code bureau"),
    ("raison_sociale", "Raison sociale client", "statut_client", "Statut client"),
    ("sigle", "Sigle", "date_creation", "Date création client"),
    ("forme_juridique", "Forme juridique", "agrement", "Agrément"),
    ("no_agrement", "N° Agrément/Arrêté n°/Décret n°", "delivre_par", "Délivré par"),
    ("no_registre_commerce", "N° registre commerce", "date_deliv_registre", "Date déliv. registre"),
    ("ninea", "NINEA", "date_deliv_ninea", "Date déliv. NINEA"),
    ("code_sous_secteur", "Code sous-secteur", "secteur", "Secteur"),
    ("telephone", "Téléphone", "email", "Email"),
    ("adresse", "Adresse", "adresse_postale", "Adresse postale"),
    ("pays", "Pays", "cotation", "Cotation"),
    ("nature", "Nature", "categorie", "Catégorie"),
    ("gestionnaire", "Gestionnaire", "sms_connect", "Sms Connect"),
    ("consentement", "Consentement ?", "numero_consentement", "Numéro Consentement"),
]

GOUVERNANCE_COLS = [
    ("prenom", "Prénom"), ("nom", "Nom"), ("fonction", "Fonction"),
    ("piece_identite", "N° pièce d'identité"), ("nationalite", "Nationalité"),
]
BENEFICIAIRE_COLS = [
    ("prenom", "Prénom"), ("nom", "Nom"), ("piece_identite", "N° pièce d'identité"),
    ("part", "Part (%)"), ("nationalite", "Nationalité"),
]
FINANCE_COLS = [
    ("annee", "Année"), ("chiffre_affaires", "Chiffre d'affaires"),
    ("resultat_net", "Résultat Net"), ("capital", "Capital"), ("effectif", "Effectif"),
]

DECLARATION_1 = (
    "Je déclare agir pour le compte de {pour_compte_de} et qui est le bénéficiaire "
    "effectif des transactions effectuées sur le compte ouvert dans vos livres."
)
DECLARATION_2 = (
    "Je déclare et garantis que les documents remis à l'institution ACEP, ainsi que "
    "les informations communiquées à cette dernière lors de l'ouverture du compte et "
    "pendant toute la durée de la relation sont exacts, réguliers et sincères."
)
DECLARATION_3 = (
    "Je m'engage, par ailleurs, à informer l'ACEP de toute modification de la "
    "situation au plus tard dans les 30 jours suivant le changement."
)


def _e(v):
    return html.escape(str(v)) if v is not None else ""


def _cell(value):
    v = _e(value)
    return v if v.strip() else "&nbsp;"


def _bloc1_table(client):
    rows = []
    for key_l, label_l, key_r, label_r in BLOC1_PAIRS:
        rows.append(
            "<tr>"
            f'<td style="border:1px solid {BORDER};padding:6px 10px;font-weight:bold;width:22%;">{_e(label_l)}</td>'
            f'<td style="border:1px solid {BORDER};padding:6px 10px;width:28%;">{_cell(client.get(key_l))}</td>'
            f'<td style="border:1px solid {BORDER};padding:6px 10px;font-weight:bold;width:22%;">{_e(label_r)}</td>'
            f'<td style="border:1px solid {BORDER};padding:6px 10px;width:28%;">{_cell(client.get(key_r))}</td>'
            "</tr>"
        )
    inner = (
        '<table style="border-collapse:collapse;width:100%;font-size:10.5pt;'
        f'font-family:Arial, sans-serif;">{"".join(rows)}</table>'
    )
    return f'<div style="border:1.5px solid {OUTER_BORDER};margin:10px 0 24px;overflow:hidden;">{inner}</div>'


def _dynamic_table(title, cols, rows):
    header_cells = "".join(
        f'<th style="border:1px solid {BORDER};padding:6px 10px;text-align:left;'
        f'color:white;">{_e(label)}</th>'
        for _, label in cols
    )
    body_rows = []
    if rows:
        for row in rows:
            cells = "".join(
                f'<td style="border:1px solid {BORDER};padding:6px 10px;">{_cell(row.get(key))}</td>'
                for key, _ in cols
            )
            body_rows.append(f"<tr>{cells}</tr>")
    else:
        colspan = len(cols)
        body_rows.append(
            f'<tr><td colspan="{colspan}" style="border:1px solid {BORDER};padding:8px 10px;'
            f'color:#888;font-style:italic;">Aucune donnée</td></tr>'
        )

    inner = (
        '<table style="border-collapse:collapse;width:100%;font-size:10.5pt;'
        f'font-family:Arial, sans-serif;">'
        f'<tr style="background:{GREEN};">{header_cells}</tr>'
        + "".join(body_rows) + "</table>"
    )
    return (
        f'<h3 style="font-size:12pt;margin:14px 0 6px;font-family:Arial, sans-serif;">{_e(title)}</h3>'
        f'<div style="border:1.5px solid {OUTER_BORDER};margin:0 0 18px;overflow:hidden;">{inner}</div>'
    )


def render_kyc_html(data):
    """
    data = {
        'date_jour': str, 'client': {...}, 'signataires': [...],
        'dirigeants': [...], 'actionnaires': [...], 'infos_fin': [...],
        'pour_compte_de': str, 'fait_a': str, 'le': str,
    }
    """
    client = data.get("client", {})
    date_jour = _e(data.get("date_jour", ""))
    pour_compte_de = _e(data.get("pour_compte_de", "……………………………………………………"))
    fait_a = _e(data.get("fait_a", ""))
    le = _e(data.get("le", ""))

    parts = []
    parts.append(
        f'<p style="text-align:right;margin:0;font-size:9pt;'
        f'font-family:Arial, sans-serif;">Date : {date_jour or "____ / ____ / ________"}</p>'
    )
    parts.append(
        '<p style="text-align:center;margin:26px 0 0;font-size:16pt;font-weight:bold;'
        'font-family:Arial, sans-serif;">FICHE KYC PERSONNE MORALE</p>'
    )
    parts.append(f'<div style="width:100%;height:3px;background:{GREEN};margin:10px 0 28px;"></div>')

    parts.append(
        '<h2 style="font-size:13pt;margin:0 0 6px;font-family:Arial, sans-serif;">1. Identification client</h2>'
    )
    parts.append(_bloc1_table(client))

    parts.append(
        '<h2 style="font-size:13pt;margin:20px 0 6px;font-family:Arial, sans-serif;">2. Gouvernance / Structure</h2>'
    )
    parts.append(_dynamic_table("Signataire", GOUVERNANCE_COLS, data.get("signataires", [])))
    parts.append(_dynamic_table("Dirigeant", GOUVERNANCE_COLS, data.get("dirigeants", [])))
    parts.append(_dynamic_table("Bénéficiaire effectif", BENEFICIAIRE_COLS, data.get("actionnaires", [])))

    parts.append(
        '<h2 style="font-size:13pt;margin:20px 0 6px;font-family:Arial, sans-serif;">3. Infos financières</h2>'
    )
    parts.append(_dynamic_table("", FINANCE_COLS, data.get("infos_fin", [])).replace(
        '<h3 style="font-size:12pt;margin:14px 0 6px;font-family:Arial, sans-serif;"></h3>', ""
    ))

    parts.append(
        f'<p style="text-align:right;margin:24px 0 20px;font-size:10.5pt;font-family:Arial, sans-serif;">'
        f'Fait à : {fait_a or "____________________________"}'
        f'&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Le : {le or "____________________________"}</p>'
    )

    decl_style = 'style="margin:8px 0;font-size:10.5pt;font-family:Arial, sans-serif;text-align:justify;"'
    parts.append(f'<p {decl_style}>{DECLARATION_1.format(pour_compte_de=pour_compte_de)}</p>')
    parts.append(f'<p {decl_style}>{DECLARATION_2}</p>')
    parts.append(f'<p {decl_style}>{DECLARATION_3}</p>')

    parts.append(
        '<table style="width:100%;margin-top:30px;font-size:10.5pt;font-family:Arial, sans-serif;">'
        '<tr>'
        '<td style="width:50%;vertical-align:top;">'
        '<p style="margin:0;font-weight:bold;">Signature du gérant :</p>'
        '<p style="margin:6px 0 0;font-size:9pt;font-style:italic;">'
        "(Précédée de la mention « je déclare sur honneur »)</p>"
        '</td>'
        '<td style="width:50%;vertical-align:top;">'
        '<p style="margin:0;font-weight:bold;">Signature ACEP :</p>'
        "</td>"
        "</tr></table>"
    )

    return "".join(parts)
