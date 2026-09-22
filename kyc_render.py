"""
Rendu HTML de la fiche KYC personne morale, dans le même style visuel que les
attestations FORMA (vert ACEP #02564A, tableaux bordés, titre souligné).

Contrairement aux attestations (template Word figé), cette fiche a des blocs
à nombre de lignes variable (signataires, dirigeants, bénéficiaires effectifs,
infos financières) : le rendu est donc construit dynamiquement en Python,
pas en remplissant un .docx existant.
"""
import base64
import html
import os

GREEN = "#02564A"
BORDER = "#D9D9D9"
OUTER_BORDER = "#1F3864"

STATUT_CLIENT_LABELS = {
    "A": "Adhérent",
    "N": "Nouveau",
    "P": "Personnel",
    "I": "Autre",
    "C": "Attente Conformité",
    "K": "Acep fekkissila",
}

OUI_NON_LABELS = {"O": "Oui", "N": "Non"}


def _label_statut_client(v):
    v = (v or "").strip().upper()
    return STATUT_CLIENT_LABELS.get(v, v)


def _label_oui_non(v):
    v = (v or "").strip().upper()
    return OUI_NON_LABELS.get(v, v)


def _prepare_client_display(client):
    """Copie du client avec les codes traduits en libellés lisibles pour l'affichage."""
    c = dict(client or {})
    c["statut_client"] = _label_statut_client(c.get("statut_client"))
    c["sms_connect"] = _label_oui_non(c.get("sms_connect"))
    c["consentement"] = _label_oui_non(c.get("consentement"))
    return c

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
    ("sous_secteur", "Sous-Secteur", "secteur", "Secteur"),
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
            f'<td style="border:1px solid {BORDER};padding:7px 12px;font-weight:bold;'
            f'width:22%;background:#F2F6F4;">{_e(label_l)}</td>'
            f'<td style="border:1px solid {BORDER};padding:7px 12px;width:28%;">{_cell(client.get(key_l))}</td>'
            f'<td style="border:1px solid {BORDER};padding:7px 12px;font-weight:bold;'
            f'width:22%;background:#F2F6F4;">{_e(label_r)}</td>'
            f'<td style="border:1px solid {BORDER};padding:7px 12px;width:28%;">{_cell(client.get(key_r))}</td>'
            "</tr>"
        )
    inner = (
        '<table style="border-collapse:collapse;width:100%;font-size:10.5pt;'
        f'font-family:Arial, sans-serif;">{"".join(rows)}</table>'
    )
    return f'<div style="border:1.5px solid {OUTER_BORDER};margin:10px 0 24px;overflow:hidden;">{inner}</div>'


def _dynamic_table(title, cols, rows):
    header_cells = "".join(
        f'<th style="border:1px solid {BORDER};padding:8px 12px;text-align:left;'
        f'color:white;font-size:9.5pt;text-transform:uppercase;letter-spacing:0.4px;">{_e(label)}</th>'
        for _, label in cols
    )
    body_rows = []
    if rows:
        for i, row in enumerate(rows):
            bg = "#ffffff" if i % 2 == 0 else "#F7FAF9"
            cells = "".join(
                f'<td style="border:1px solid {BORDER};padding:7px 12px;background:{bg};">{_cell(row.get(key))}</td>'
                for key, _ in cols
            )
            body_rows.append(f"<tr>{cells}</tr>")
    else:
        colspan = len(cols)
        body_rows.append(
            f'<tr><td colspan="{colspan}" style="border:1px solid {BORDER};padding:9px 12px;'
            f'color:#888;font-style:italic;">Aucune donnée</td></tr>'
        )

    inner = (
        '<table style="border-collapse:collapse;width:100%;font-size:10.5pt;'
        f'font-family:Arial, sans-serif;">'
        f'<tr style="background:{GREEN};">{header_cells}</tr>'
        + "".join(body_rows) + "</table>"
    )
    title_html = (
        f'<h3 style="font-size:11.5pt;margin:14px 0 6px;font-family:Arial, sans-serif;'
        f'color:{GREEN};">{_e(title)}</h3>'
        if title else ""
    )
    return (
        title_html
        + f'<div style="border:1.5px solid {OUTER_BORDER};margin:0 0 18px;overflow:hidden;'
        f'border-radius:3px;">{inner}</div>'
    )


def render_kyc_html(data, include_date_line=True):
    """
    data = {
        'date_jour': str, 'client': {...}, 'signataires': [...],
        'dirigeants': [...], 'actionnaires': [...], 'infos_fin': [...],
        'pour_compte_de': str, 'fait_a': str, 'le': str,
    }

    include_date_line=False permet d'omettre la ligne "Date : ..." en tête de
    document : utilisé par le rendu PDF, où la date est affichée dans l'en-tête
    de page (uniquement sur la 1re page) plutôt que dans le corps du texte.
    """
    client = _prepare_client_display(data.get("client", {}))
    date_jour = _e(data.get("date_jour", ""))
    pour_compte_de = _e(data.get("pour_compte_de", "……………………………………………………"))
    fait_a = _e(data.get("fait_a", ""))
    le = _e(data.get("le", ""))

    parts = []
    if include_date_line:
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
        f'Fait à {fait_a or "____________________________"}'
        f'&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Le {le or "____________________________"}</p>'
    )

    decl_style = 'style="margin:8px 0;font-size:10.5pt;font-family:Arial, sans-serif;text-align:justify;"'
    parts.append(f'<p {decl_style}>{DECLARATION_1.format(pour_compte_de=pour_compte_de)}</p>')
    parts.append(f'<p {decl_style}>{DECLARATION_2}</p>')
    parts.append(f'<p {decl_style}>{DECLARATION_3}</p>')

    # Bloc signature : une seule ligne "Signature du gérant :  …  Signature ACEP"
    # (comme dans le document Word source, qui n'utilise pas de tableau ici),
    # suivie de la mention en petit, sur toute la largeur.
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


def _logo_data_uri():
    """Encode le logo ACEP en base64 pour l'en-tête répété du PDF (évite toute
    dépendance à un chemin de fichier accessible depuis le moteur PDF)."""
    path = os.path.join(os.path.dirname(__file__), "static", "logo_acep.png")
    try:
        with open(path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("ascii")
        return f"data:image/png;base64,{b64}"
    except OSError:
        return ""


def render_kyc_pdf_html(data):
    """
    Document HTML complet (avec <html>/<head>/<body> et règles @page CSS)
    utilisé pour générer le PDF de la fiche KYC via WeasyPrint.

    Contrairement à render_kyc_html() (qui ne produit qu'un fragment pour
    l'aperçu écran), ce document définit un en-tête répété sur chaque page
    (logo + "ACEP", via un élément "running") et un pied de page avec
    numérotation ("Page X / Y", via les compteurs CSS natifs) — deux choses
    que le moteur d'impression natif du navigateur ne sait pas faire.
    """
    # include_date_line=False : la date n'est plus dans le corps du texte,
    # elle est affichée dans l'en-tête de page (uniquement page 1, voir @page :first).
    body = render_kyc_html(data, include_date_line=False)
    date_jour = _e(data.get("date_jour", "")) or "____ / ____ / ________"
    logo_uri = _logo_data_uri()
    logo_img = (
        f'<img src="{logo_uri}" style="height:22px;vertical-align:middle;margin-right:8px;">'
        if logo_uri else ""
    )

    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>Fiche KYC</title>
<style>
  @page {{
    size: A4;
    margin: 2.2cm 1.9cm 1.7cm 1.9cm;
    @top-left {{ content: element(pageHeader); vertical-align: middle; }}
    @bottom-center {{
      content: "Page " counter(page) " / " counter(pages);
      font-family: Arial, sans-serif;
      font-size: 8.5pt;
      color: #666666;
    }}
  }}
  @page :first {{
    @top-right {{ content: element(pageDate); vertical-align: middle; }}
  }}
  #page-header {{
    position: running(pageHeader);
    display: flex;
    align-items: center;
    justify-content: flex-start;
    font-family: Arial, sans-serif;
  }}
  #page-header .name {{
    font-size: 13pt;
    font-weight: bold;
    color: {GREEN};
    letter-spacing: 0.6px;
  }}
  #page-date {{
    position: running(pageDate);
    font-family: Arial, sans-serif;
    font-size: 9pt;
    color: #666666;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    font-family: Arial, sans-serif;
    color: #1a1a1a;
    margin: 0;
  }}
  table {{ border-collapse: collapse; }}
</style>
</head>
<body>
  <div id="page-header">{logo_img}<span class="name">ACEP</span></div>
  <div id="page-date">Date : {date_jour}</div>
  {body}
</body>
</html>"""


def generate_kyc_pdf(data):
    """Retourne les octets du PDF de la fiche KYC, avec en-tête (logo + ACEP)
    et numérotation de pages répétés automatiquement par WeasyPrint."""
    from weasyprint import HTML

    html_doc = render_kyc_pdf_html(data)
    return HTML(string=html_doc, base_url=os.path.dirname(__file__)).write_pdf()
