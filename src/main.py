import os
import sys
from flask import Flask, send_from_directory
from flask_cors import CORS

# ضَع تعديل المسار قبل استيرادات src.*
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src.models.user import db, User
from src.models.tagging import TaggingData, TaggingReview, UploadSession
from src.routes.user import user_bp
from src.routes.tagging import tagging_bp

app = Flask(__name__, static_folder=os.path.join(os.path.dirname(__file__), 'static'))
app.config['SECRET_KEY'] = 'tagging-platform-secret-key-2024-final'

# CORS
CORS(app, supports_credentials=True)

# Blueprints
app.register_blueprint(user_bp, url_prefix='/api')
app.register_blueprint(tagging_bp, url_prefix='/api/tagging')

# =========================
# Database configuration
# =========================
db_uri = os.getenv('SQLALCHEMY_DATABASE_URI') or os.getenv('DATABASE_URL')
if not db_uri:
    raise RuntimeError("SQLALCHEMY_DATABASE_URI is not set in the environment.")

# توافق لمسارات قديمة
if db_uri.startswith('postgres://'):
    db_uri = db_uri.replace('postgres://', 'postgresql://', 1)

# SSL عند الاتصال الخارجي
if 'sslmode=' not in db_uri and 'localhost' not in db_uri:
    db_uri += ('&' if '?' in db_uri else '?') + 'sslmode=require'

app.config['SQLALCHEMY_DATABASE_URI'] = db_uri
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# تهيئة قاعدة البيانات
db.init_app(app)

# --- إعداد تلقائي: ترقية العمود وإنشاء أدمن ---
with app.app_context():
    # 1) إنشاء الجداول إن لم توجد
    try:
        db.create_all()
    except Exception as e:
        print("DB init error:", e)

    # 2) ترقية طول عمود password_hash إلى 255 لتفادي تقصير النص
    try:
        from sqlalchemy import text
        with db.engine.begin() as conn:
            conn.execute(text(
                "ALTER TABLE users "
                "ALTER COLUMN password_hash TYPE VARCHAR(255)"
            ))
            # ملاحظة: لو العمود أصلاً 255 أو Text فالأمر قد يرمي خطأ بسيط؛ نتجاهله بالكتش التالي
        print("password_hash column ensured to VARCHAR(255).")
    except Exception as e:
        print("Skip/ignore password_hash alter (maybe already large enough):", e)

    # 3) إنشاء/تحديث مستخدم admin بكلمة مرور مُجزّأة
    try:
        cols = User.__table__.columns.keys()
        admin = User.query.filter_by(username='admin').first()

        if not admin:
            admin = User(username='admin')

            # نوع المستخدم إن وُجد
            if 'user_type' in cols:
                admin.user_type = 'admin'
            elif 'role' in cols:
                admin.role = 'admin'

            # استخدم set_password إن توفّر
            if hasattr(admin, 'set_password') and callable(getattr(admin, 'set_password')):
                admin.set_password('admin123')
            else:
                # احتياطي: خزن بالـ hash في password_hash أو نصيًا في password حسب الأعمدة
                from werkzeug.security import generate_password_hash
                if 'password_hash' in cols:
                    admin.password_hash = generate_password_hash('admin123')
                elif 'password' in cols:
                    admin.password = 'admin123'
                else:
                    raise RuntimeError("No password field found on User model.")

            db.session.add(admin)
            db.session.commit()
            print("Admin created: username=admin, password=admin123")
        else:
            needs_commit = False
            # تأكد من تعيين الدور
            if 'user_type' in cols and (getattr(admin, 'user_type', None) or '').lower() != 'admin':
                admin.user_type = 'admin'; needs_commit = True
            if 'role' in cols and (getattr(admin, 'role', None) or '').lower() != 'admin':
                admin.role = 'admin'; needs_commit = True
            # تأكد من وجود كلمة مرور مُهيأة
            if hasattr(admin, 'password_hash') and not getattr(admin, 'password_hash', None):
                if hasattr(admin, 'set_password') and callable(getattr(admin, 'set_password')):
                    admin.set_password('admin123'); needs_commit = True
            if needs_commit:
                db.session.commit()
                print("Admin fields updated.")
            else:
                print("Admin user already exists and is configured.")
    except Exception as e:
        print("Admin creation error:", e)
# --- نهاية الإعداد التلقائي ---

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve(path):
    """
    يقدم ملفات الواجهة الثابتة و index.html لتطبيق SPA.
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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
