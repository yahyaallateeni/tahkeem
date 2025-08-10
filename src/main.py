import os
import sys
from flask import Flask, send_from_directory
from flask_cors import CORS
from src.models.user import db, User
from src.models.tagging import TaggingData, TaggingReview, UploadSession
from src.routes.user import user_bp
from src.routes.tagging import tagging_bp
from werkzeug.security import generate_password_hash

# Ensure project structure path is loaded before imports from src.*
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

app = Flask(__name__, static_folder=os.path.join(os.path.dirname(__file__), 'static'))
app.config['SECRET_KEY'] = 'tagging-platform-secret-key-2024-final'

# Enable CORS for all routes to allow connections from different domains.
CORS(app, supports_credentials=True)

# Register blueprints to organize your routes.
app.register_blueprint(user_bp, url_prefix='/api')
app.register_blueprint(tagging_bp, url_prefix='/api/tagging')

# =========================
# Database configuration
# =========================
db_uri = os.getenv('SQLALCHEMY_DATABASE_URI') or os.getenv('DATABASE_URL')
if not db_uri:
    raise RuntimeError("SQLALCHEMY_DATABASE_URI is not set in the environment.")
if db_uri.startswith('postgres://'):
    db_uri = db_uri.replace('postgres://', 'postgresql://', 1)
if 'sslmode=' not in db_uri and 'localhost' not in db_uri:
    db_uri += ('&' if '?' in db_uri else '?') + 'sslmode=require'

app.config['SQLALCHEMY_DATABASE_URI'] = db_uri
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize the database with the Flask app.
db.init_app(app)

# --- AUTO DB INIT & FLEXIBLE ADMIN CREATION ---
with app.app_context():
    # Create tables if they don't exist
    try:
        db.create_all()
    except Exception as e:
        print("DB init error:", e)

    try:
        # If admin user doesn't exist, create one
        admin = User.query.filter_by(username='admin').first()
        if not admin:
            admin = User()
            # Mandatory username
            setattr(admin, 'username', 'admin')

            # Decide where to store the password:
            # 1) If model has password_hash column -> store hashed
            if 'password_hash' in getattr(User, '__table__').columns:
                setattr(admin, 'password_hash', generate_password_hash('admin123'))
            # 2) Else if model has password column -> store plaintext
            elif 'password' in getattr(User, '__table__').columns:
                setattr(admin, 'password', 'admin123')
            else:
                # No known password field; fail gracefully with a clear log
                raise RuntimeError(
                    "User model has neither 'password_hash' nor 'password' column."
                )

            # Optional role if exists
            if 'role' in getattr(User, '__table__').columns:
                setattr(admin, 'role', 'admin')

            db.session.add(admin)
            db.session.commit()
            print("Admin user created: username=admin, password=admin123")
        else:
            print("Admin user already exists.")
    except Exception as e:
        print("Admin creation error:", e)
# --- END AUTO SETUP ---

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve(path):
    """
    Serves the static files and the main index.html for the single-page application.
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

# Main entry point for local development.
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
