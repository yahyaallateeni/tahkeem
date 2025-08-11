import os
import sys
from datetime import timedelta
from flask import Flask, send_from_directory, jsonify, session, request
from flask_cors import CORS

# ضف مسار جذر المشروع حتى تعمل استيرادات src.*
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src.config import get_secret_key
from src.models.user import db
from src.models.tagging import TaggingData, TaggingReview, UploadSession  # noqa: F401
from src.routes.user import user_bp
from src.routes.tagging import tagging_bp

# ===== إنشاء التطبيق والملفات الثابتة =====
app = Flask(__name__, static_folder=os.path.join(os.path.dirname(__file__), 'static'))
app.config['SECRET_KEY'] = get_secret_key()

# إعدادات الجلسة (مهم لحفظ الكوكي على HTTPS/Render)
app.config.update(
    SESSION_COOKIE_NAME='tahkeem_session',
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SECURE=True,    # Render يعمل HTTPS
    SESSION_COOKIE_SAMESITE='Lax', # مناسب لنفس الدومين
    PERMANENT_SESSION_LIFETIME=timedelta(days=7),
    SESSION_PERMANENT=True,
)

# CORS (نفس الأصل، لكن نترك الدعم للمستقبل)
CORS(app, supports_credentials=True)

# قاعدة البيانات
db_uri = os.getenv('SQLALCHEMY_DATABASE_URI') or os.getenv('DATABASE_URL')
if not db_uri:
    raise RuntimeError("SQLALCHEMY_DATABASE_URI is not set in the environment.")
if db_uri.startswith('postgres://'):
    db_uri = db_uri.replace('postgres://', 'postgresql://', 1)
if 'sslmode=' not in db_uri and 'localhost' not in db_uri:
    db_uri += ('&' if '?' in db_uri else '?') + 'sslmode=require'
app.config['SQLALCHEMY_DATABASE_URI'] = db_uri
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

# تسجيل المسارات
app.register_blueprint(user_bp, url_prefix='/api')
app.register_blueprint(tagging_bp, url_prefix='/api/tagging')

# ===== تهيئة الجداول =====
with app.app_context():
    db.create_all()

# ====== نقاط فحص سريعة (لا تُكسر الواجهة) ======
@app.get('/api/health')
def api_health():
    return jsonify({'ok': True})

@app.get('/api/debug/session')
def api_debug_session():
    return jsonify({
        'logged_in': 'user_id' in session,
        'user_id': session.get('user_id'),
        'username': session.get('username'),
        'user_type': session.get('user_type'),
        'cookies_seen': request.cookies.keys()
    })

# ====== مُعالِجات أخطاء تُرجع JSON واضح ======
@app.errorhandler(401)
def err_401(e):
    return jsonify({'error': 'unauthorized'}), 401

@app.errorhandler(403)
def err_403(e):
    return jsonify({'error': 'forbidden'}), 403

@app.errorhandler(404)
def err_404(e):
    return jsonify({'error': 'not_found'}), 404

@app.errorhandler(Exception)
def err_500(e):
    # إرجاع تفاصيل مبسطة للعميل + الطباعة في اللوج
    try:
        import traceback
        traceback.print_exc()
    except Exception:
        pass
    return jsonify({'error': 'server_error', 'details': str(e)}), 500

# ===== تقديم واجهة SPA =====
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
