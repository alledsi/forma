# UM-ACEP — Générateur d'attestations (prototype)

## Installation
```
pip install -r requirements.txt
```

## Lancement
```
python app.py
```
Puis ouvrir http://localhost:5000

## Fonctionnement
- `templates_docx/` : les 4 templates Word originaux (source de vérité, ne pas renommer)
- `doc_engine.py` : logique de remplissage — mapping champ → cellule du tableau pour chaque type de document
- `app.py` : serveur Flask (page d'accueil + endpoint `/preview`)
- `templates/index.html` : interface (sélection du type, formulaire dynamique, aperçu à l'écran)

## Aucun téléchargement
Le document n'est jamais envoyé en fichier .docx au navigateur. Le serveur génère le document,
le convertit en aperçu HTML en lecture seule, et l'utilisateur ne peut que l'imprimer (bouton
"Imprimer", qui déclenche l'impression du navigateur limitée à la zone d'aperçu). Cela évite
que l'utilisateur récupère et modifie le fichier Word source.

## Documents disponibles
1. Attestation de solde
2. Attestation de capacité financière
3. Attestation de non engagement (prêt soldé)
4. Attestation d'engagement (prêt actif)

## Ajouter un nouveau type de document
Ajouter une entrée dans `DOC_TYPES` (doc_engine.py) avec le fichier template, la liste des champs,
et le `row_map` (index de ligne du tableau → clé de champ). Placer le template `.docx` dans `templates_docx/`.
