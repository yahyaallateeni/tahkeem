from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import uuid
import json
from datetime import datetime

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(120), nullable=False)
    user_type = db.Column(db.String(20), nullable=False, default="reviewer")  # "admin" or "reviewer"
    email = db.Column(db.String(120), nullable=True)
    created_by = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'user_type': self.user_type,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class Sentence(db.Model):
    __tablename__ = "sentences"
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    text = db.Column(db.Text, nullable=False)
    original_tags_json = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    annotations = db.relationship("Annotation", back_populates="sentence", cascade="all, delete-orphan")
    
    def get_original_tags(self):
        if self.original_tags_json:
            try:
                return json.loads(self.original_tags_json)
            except:
                return {}
        return {}
    
    def to_dict(self):
        return {
            'id': self.id,
            'text': self.text,
            'original_tags': self.get_original_tags(),
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class Annotation(db.Model):
    __tablename__ = "annotations"
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    sentence_id = db.Column(db.String(36), db.ForeignKey("sentences.id"), nullable=False)
    tag_key = db.Column(db.String(100), nullable=False)
    tag_value = db.Column(db.String(200), nullable=False)
    is_correct = db.Column(db.Boolean, default=None)
    reviewer_comment = db.Column(db.Text, default="")
    reviewer_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=True)
    reviewed_at = db.Column(db.DateTime, nullable=True)
    sentence = db.relationship("Sentence", back_populates="annotations")
    reviewer = db.relationship("User", foreign_keys=[reviewer_id])
    
    def to_dict(self):
        return {
            'id': self.id,
            'sentence_id': self.sentence_id,
            'tag_key': self.tag_key,
            'tag_value': self.tag_value,
            'is_correct': self.is_correct,
            'reviewer_comment': self.reviewer_comment,
            'reviewed_at': self.reviewed_at.isoformat() if self.reviewed_at else None
        }

class ContactMessage(db.Model):
    __tablename__ = "contact_messages"
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    sender_name = db.Column(db.String(100), nullable=False)
    sender_email = db.Column(db.String(120), nullable=False)
    message = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'sender_name': self.sender_name,
            'sender_email': self.sender_email,
            'message': self.message,
            'is_read': self.is_read,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

