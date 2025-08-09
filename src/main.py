import os
import sys
import subprocess
from flask import Flask, send_from_directory
from flask_cors import CORS
from src.models.user import db
from src.models.tagging import TaggingData, TaggingReview, UploadSession
from src.routes.user import user_bp
from src.routes.tagging import tagging_bp

# This is an important step to ensure the project structure is correctly handled.
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

app = Flask(__name__, static_folder=os.path.join(os.path.dirname(__file__), 'static'))
app.config['SECRET_KEY'] = 'tagging-platform-secret-key-2024-final'

# Enable CORS for all routes to allow connections from different domains.
CORS(app, supports_credentials=True)

# Register blueprints to organize your routes.
app.register_blueprint(user_bp, url_prefix='/api')
app.register_blueprint(tagging_bp, url_prefix='/api/tagging')

# Database configuration
# This now gets the database connection string from the environment variable set on Render.
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize the database with the Flask app.
db.init_app(app)

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

# Main entry point for the application.
if __name__ == '__main__':
    with app.app_context():
        # This will create all the database tables in the PostgreSQL database.
        db.create_all()
    
        # This temporary code runs the create_admin.py script to set up the admin user.
        # It's important to run this after db.create_all() to ensure the tables exist.
        print("Running create_admin.py script...")
        try:
            subprocess.run(['python', 'src/create_admin.py'], check=True, cwd=os.path.dirname(__file__))
            print("create_admin.py script finished.")
        except subprocess.CalledProcessError as e:
            print(f"Error running create_admin.py: {e}")
            
    # Starts the Flask development server.
    app.run(host='0.0.0.0', port=5000, debug=True)
