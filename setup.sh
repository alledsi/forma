#!/bin/bash
# Crée un environnement virtuel et installe les dépendances.
set -e
cd "$(dirname "$0")"

python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo ""
echo "Environnement prêt. Pour lancer l'app :"
echo "  source venv/bin/activate"
echo "  python app.py"
