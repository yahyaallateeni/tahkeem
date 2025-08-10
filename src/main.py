import os
import sys
from flask import Flask, send_from_directory, jsonify
from flask_cors import CORS

# اجعل مسار src متاحاً قبل الاستيراد
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src.models.user import db, User
from src.models.tagging import TaggingData, TaggingReview, UploadSession
from src.routes.user import user_bp
from src.routes.tagging import tagging_bp

# -------------------------
# Flask app & basic configs
# -------------------------
app = Flask(__name__, static_folder=os.path.join(os.path.dirname(__file__), 'static'))
app.config['SECRET_KEY'] = 'tagging-platform-secret-key-2024-final'

# كوكي الجلسة مناسبة لـ HTTPS على Render
app.config['SESSION_COOKIE_SAMESITE'] = 'None'
app.config['SESSION_COOKIE_SECURE'] = True

# فعّل CORS مع دعم الكوكي
CORS(app, supports_credentials=True)

# سجّل Blueprints
app.register_blueprint(user_bp, url_prefix='/api')
app.register_blueprint(tagging_bp, url_prefix='/api/tagging')

# -------------------------
# Database configuration
# -------------------------
db_uri = os.getenv('SQLALCHEMY_DATABASE_URI') or os.getenv('DATABASE_URL')
if not db_uri:
    raise RuntimeError("SQLALCHEMY_DATABASE_URI or DATABASE_URL must be set.")

# توافق لمسارات قديمة
if db_uri.startswith('postgres://'):
    db_uri = db_uri.replace('postgres://', 'postgresql://', 1)

# SSL عند الاتصال الخارجي
if 'sslmode=' not in db_uri and 'localhost' not in db_uri:
    db_uri += ('&' if '?' in db_uri else '?') + 'sslmode=require'

app.config['SQLALCHEMY_DATABASE_URI'] = db_uri
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

# -------------------------------------
# Auto setup: migrate & ensure admin
# -------------------------------------
with app.app_context():
    # 1) إنشاء الجداول إن لم تكن موجودة
    try:
        db.create_all()
    except Exception as e:
        print("DB init error:", e)

    # 2) كبّر عمود password_hash إلى TEXT لتفادي تقصير الهاش
    try:
        from sqlalchemy import text
        with db.engine.begin() as conn:
            conn.execute(text("ALTER TABLE users ALTER COLUMN password_hash TYPE TEXT"))
        print("password_hash column set to TEXT.")
    except Exception as e:
        # لو كان بالفعل TEXT أو مناسب؛ تجاهل
        print("Skip/ignore password_hash alter (maybe already TEXT):", e)

    # 3) احذف أي admin قديم (تفادي بيانات تالفة) ثم أنشئه من جديد
    try:
        from sqlalchemy import text
        db.session.execute(text("DELETE FROM users WHERE username = 'admin'"))
        db.session.commit()
        print("Old admin rows deleted (if existed).")
    except Exception as e:
        db.session.rollback()
        print("Skip admin delete:", e)

    try:
        cols = set(User.__table__.columns.keys())
        admin = User(username='admin')

        # اضبط الدور إن وُجد
        if 'user_type' in cols:
            admin.user_type = 'admin'
        elif 'role' in cols:
            admin.role = 'admin'

        # عيّن كلمة المرور (متوافقة مع check_password)
        if hasattr(admin, 'set_password') and callable(getattr(admin, 'set_password')):
            admin.set_password('admin123')
        else:
            from werkzeug.security import generate_password_hash
            if 'password_hash' in cols:
                admin.password_hash = generate_password_hash('admin123')
            elif 'password' in cols:
                admin.password = 'admin123'
            else:
                raise RuntimeError("No password field found on User model.")

        db.session.add(admin)
        db.session.commit()
        print("Admin ready: username=admin, password=admin123")
    except Exception as e:
        db.session.rollback()
        print("Admin creation/reset error:", e)

# -------------------------
# Error handlers (JSON only)
# -------------------------
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

# -------------------------
# Static SPA serving
# -------------------------
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve(path):
    """
    يقدم ملفات الواجهة الثابتة من src/static
    """
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

# -------------------------
# Local dev entry
# -------------------------
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
