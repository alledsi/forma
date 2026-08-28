"""
Plateforme de génération de documents UM-ACEP — prototype.
Lancer avec : python app.py
Puis ouvrir : http://localhost:5000
"""
from flask import Flask, render_template, request, jsonify
from doc_engine import DOC_TYPES, generate_preview_html

app = Flask(__name__)


@app.route("/")
def index():
    # On n'envoie au front que ce qui est nécessaire (pas row_map/date_in_label_row)
    doc_types_public = {
        key: {
            "label": cfg["label"],
            "description": cfg.get("description", ""),
            "icon": cfg.get("icon", "📄"),
            "fields": cfg["fields"],
        }
        for key, cfg in DOC_TYPES.items()
    }
    return render_template("index.html", doc_types=doc_types_public)


@app.route("/preview", methods=["POST"])
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


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
