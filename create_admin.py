#!/usr/bin/env python3
import os
import sys

# Add the project directory to Python path
project_dir = '/home/ubuntu/tagging-platform-final'
sys.path.insert(0, project_dir)

from flask import Flask
from src.models.user import db, User

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{project_dir}/src/database/app.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

with app.app_context():
    # Create tables if they don't exist
    db.create_all()
    
    # Check if admin exists
    admin = User.query.filter_by(username='admin').first()
    if admin:
        print('Admin user already exists')
        print(f'Username: {admin.username}')
        print(f'User type: {admin.user_type}')
        print(f'Email: {admin.email}')
    else:
        # Create admin user
        admin = User(username='admin', user_type='admin', email='admin@example.com')
        admin.set_password('admin123')
        db.session.add(admin)
        db.session.commit()
        print('Admin user created successfully')
        print('Username: admin')
        print('Password: admin123')
        print('Type: admin')

