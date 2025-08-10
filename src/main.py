import os
import sys
import subprocess
from flask import Flask, send_from_directory, jsonify
from flask_cors import CORS
from src.models.user import db
from src.models.tagging import TaggingData, TaggingReview, UploadSession
from src.routes.user import user_bp
from src.routes.tagging import tagging_bp

# لضبط المسار
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

app = Flask(__name__, static_folder=os.path.join(os.path.dirname(__file__), 'static'))
app.config['SECRET_KEY'] = 'tagging-platform-secret-key-2024-final'

# تفعيل CORS مع الكوكيز
CORS(app, supports_credentials=True)

# تسجيل الـ Blueprints
app.register_blueprint(user_bp, url_prefix='/api')
app.register_blueprint(tagging_bp, url_prefix='/api/tagging')

# إعداد قاعدة البيانات
db_uri = os.getenv('SQLALCHEMY_DATABASE_URI') or os.getenv('DATABASE_URL')
if not db_uri:
    raise RuntimeError("SQLALCHEMY_DATABASE_URI or DATABASE_URL must be set.")

if db_uri.startswith('postgres://'):
    db_uri = db_uri.replace('postgres://', 'postgresql://', 1)

if 'sslmode=' not in db_uri and 'localhost' not in db_uri:
    db_uri += ('&' if '?' in db_uri else '?') + 'sslmode=require'

app.config['SQLALCHEMY_DATABASE_URI'] = db_uri
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

with app.app_context():
    db.create_all()
    print("Running create_admin.py script...")
    try:
        subprocess.run(['python', 'src/create_admin.py'], check=True, cwd=os.path.dirname(__file__))
        print("create_admin.py script finished.")
    except subprocess.CalledProcessError as e:
        print(f"Error running create_admin.py: {e}")

# 📌 معالجات الأخطاء حتى نرجع JSON بدل HTML
@app.errorhandler(500)
def handle_500(e):
    return jsonify({"error": "server_error", "message": str(e)}), 500

@app.errorhandler(404)
def handle_404(e):
    return jsonify({"error": "not_found"}), 404

@app.errorhandler(403)
def handle_403(e):
    return jsonify({"error": "forbidden"}), 403

@app.errorhandler(401)
def handle_401(e):
    return jsonify({"error": "unauthorized"}), 401

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve(path):
    static_folder_path = app.static_folder
    if static_folder_path is None:
        return "Static folder not configured", 404

    if path != "" and os.path.exists(os.path.join(static_folder_path, path)):
        return send_from_directory(static_folder_path, path)
    else:
        index_path = os.path.join(static_folder_path, 'index.html')
        if os.path.exists(index_path):
            return send_from_directory(static_folder_path, 'index.html')
        else:
            return "index.html not found", 404

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
