from flask import Blueprint, request, jsonify, session
from src.models.user import User, Sentence, Annotation, ContactMessage, db
import csv
import os
import tempfile
import json
import chardet
from werkzeug.utils import secure_filename
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

user_bp = Blueprint('user', __name__)

# Authentication routes
@user_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json() if request.is_json else request.form
    username = data.get('username')
    password = data.get('password')
    
    if not username or not password:
        return {"detail": "اسم المستخدم وكلمة المرور مطلوبان"}, 400
    
    user = User.query.filter_by(username=username).first()
    if not user or not user.check_password(password):
        return {"detail": "اسم المستخدم أو كلمة المرور غير صحيحة"}, 401
    
    session['user_id'] = user.id
    session['username'] = user.username
    session['user_type'] = user.user_type
    
    return {
        "access_token": "session_based", 
        "token_type": "session",
        "user_type": user.user_type,
        "username": user.username,
        "message": "تم تسجيل الدخول بنجاح"
    }

@user_bp.route('/logout', methods=['POST'])
def logout():
    session.clear()
    return {"message": "تم تسجيل الخروج بنجاح"}

@user_bp.route('/check-session', methods=['GET'])
def check_session():
    if 'user_id' in session:
        return {
            "user_type": session.get('user_type'),
            "username": session.get('username'),
            "logged_in": True
        }
    else:
        return {"logged_in": False}, 401

@user_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json() if request.is_json else request.form
    username = data.get('username')
    password = data.get('password')
    email = data.get('email', '')
    
    if not username or not password:
        return {"detail": "اسم المستخدم وكلمة المرور مطلوبان"}, 400
    
    # Check if user exists
    existing_user = User.query.filter_by(username=username).first()
    if existing_user:
        return {"detail": "اسم المستخدم موجود بالفعل"}, 400
    
    # Create new user (default type is reviewer)
    user = User(username=username, email=email, user_type="reviewer")
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    
    return {"message": "تم إنشاء الحساب بنجاح"}

# Admin routes
@user_bp.route('/admin/users', methods=['GET'])
def get_all_users():
    if session.get('user_type') != 'admin':
        return {"detail": "غير مصرح لك بالوصول"}, 403
    
    users = User.query.all()
    return jsonify([user.to_dict() for user in users])

@user_bp.route('/admin/users', methods=['POST'])
def create_user_by_admin():
    if session.get('user_type') != 'admin':
        return {"detail": "غير مصرح لك بالوصول"}, 403
    
    data = request.get_json() if request.is_json else request.form
    username = data.get('username')
    password = data.get('password')
    email = data.get('email', '')
    user_type = data.get('user_type', 'reviewer')
    
    if not username or not password:
        return {"detail": "اسم المستخدم وكلمة المرور مطلوبان"}, 400
    
    # Check if user exists
    existing_user = User.query.filter_by(username=username).first()
    if existing_user:
        return {"detail": "اسم المستخدم موجود بالفعل"}, 400
    
    # Create new user
    user = User(username=username, email=email, user_type=user_type, created_by=session.get('user_id'))
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    
    return {"message": "تم إنشاء المستخدم بنجاح", "user": user.to_dict()}

@user_bp.route('/admin/users/<user_id>', methods=['DELETE'])
def delete_user_by_admin(user_id):
    if session.get('user_type') != 'admin':
        return {"detail": "غير مصرح لك بالوصول"}, 403
    
    user = User.query.get_or_404(user_id)
    
    # Prevent admin from deleting themselves
    if user.id == session.get('user_id'):
        return {"detail": "لا يمكنك حذف حسابك الخاص"}, 400
    
    db.session.delete(user)
    db.session.commit()
    
    return {"message": "تم حذف المستخدم بنجاح"}

# Data upload routes
@user_bp.route('/upload', methods=['POST'])
def upload_csv():
    if 'file' not in request.files:
        return {"detail": "لم يتم اختيار ملف"}, 400
    
    file = request.files['file']
    if file.filename == '':
        return {"detail": "لم يتم اختيار ملف"}, 400
    
    if not file.filename.endswith('.csv'):
        return {"detail": "يجب أن يكون الملف من نوع CSV"}, 400
    
    try:
        # Read file content
        file_content = file.read()
        
        # Detect encoding
        detected = chardet.detect(file_content)
        encoding = detected['encoding'] or 'utf-8'
        
        # Decode content
        content = file_content.decode(encoding)
        
        # Parse CSV
        csv_reader = csv.DictReader(content.splitlines())
        
        sentences_added = 0
        for row in csv_reader:
            if 'text' in row:
                # Create sentence
                sentence = Sentence(text=row['text'])
                
                # Store original tags as JSON
                tags = {}
                for key, value in row.items():
                    if key != 'text' and value:
                        tags[key] = value
                
                if tags:
                    sentence.original_tags_json = json.dumps(tags, ensure_ascii=False)
                
                db.session.add(sentence)
                
                # Create annotations for each tag
                for tag_key, tag_value in tags.items():
                    annotation = Annotation(
                        sentence=sentence,
                        tag_key=tag_key,
                        tag_value=tag_value
                    )
                    db.session.add(annotation)
                
                sentences_added += 1
        
        db.session.commit()
        return {"message": f"تم رفع {sentences_added} جملة بنجاح"}
        
    except Exception as e:
        return {"detail": f"خطأ في معالجة الملف: {str(e)}"}, 400

# Review routes
@user_bp.route('/review/pending', methods=['GET'])
def get_pending_reviews():
    # Get annotations that haven't been reviewed yet
    pending = Annotation.query.filter_by(is_correct=None).limit(50).all()
    
    result = []
    for annotation in pending:
        result.append({
            'annotation': annotation.to_dict(),
            'sentence': annotation.sentence.to_dict()
        })
    
    return jsonify(result)

@user_bp.route('/review/<annotation_id>', methods=['POST'])
def submit_review(annotation_id):
    data = request.get_json() if request.is_json else request.form
    is_correct = data.get('is_correct')
    comment = data.get('comment', '')
    
    annotation = Annotation.query.get_or_404(annotation_id)
    annotation.is_correct = is_correct
    annotation.reviewer_comment = comment
    annotation.reviewer_id = session.get('user_id')
    annotation.reviewed_at = datetime.utcnow()
    
    db.session.commit()
    
    return {"message": "تم حفظ المراجعة بنجاح"}

# Statistics routes
@user_bp.route('/stats', methods=['GET'])
def get_statistics():
    total_sentences = Sentence.query.count()
    total_annotations = Annotation.query.count()
    reviewed_annotations = Annotation.query.filter(Annotation.is_correct.isnot(None)).count()
    pending_annotations = Annotation.query.filter_by(is_correct=None).count()
    
    stats = {
        'total_sentences': total_sentences,
        'total_annotations': total_annotations,
        'reviewed_annotations': reviewed_annotations,
        'pending_annotations': pending_annotations,
        'completion_rate': round((reviewed_annotations / total_annotations * 100) if total_annotations > 0 else 0, 2)
    }
    
    return jsonify(stats)

# Contact routes
@user_bp.route('/contact', methods=['POST'])
def submit_contact():
    data = request.get_json() if request.is_json else request.form
    sender_name = data.get('sender_name')
    sender_email = data.get('sender_email')
    message = data.get('message')
    
    if not all([sender_name, sender_email, message]):
        return {"detail": "جميع الحقول مطلوبة"}, 400
    
    # Save to database
    contact_msg = ContactMessage(
        sender_name=sender_name,
        sender_email=sender_email,
        message=message
    )
    db.session.add(contact_msg)
    db.session.commit()
    
    # Send email (simplified - in production use proper email service)
    try:
        send_contact_email(sender_name, sender_email, message)
        return {"message": "تم إرسال رسالتك بنجاح"}
    except Exception as e:
        return {"message": "تم حفظ رسالتك وسيتم الرد عليك قريباً"}

@user_bp.route('/admin/messages', methods=['GET'])
def get_contact_messages():
    if session.get('user_type') != 'admin':
        return {"detail": "غير مصرح لك بالوصول"}, 403
    
    messages = ContactMessage.query.order_by(ContactMessage.created_at.desc()).all()
    return jsonify([msg.to_dict() for msg in messages])

@user_bp.route('/admin/messages/<message_id>/read', methods=['POST'])
def mark_message_read(message_id):
    if session.get('user_type') != 'admin':
        return {"detail": "غير مصرح لك بالوصول"}, 403
    
    message = ContactMessage.query.get_or_404(message_id)
    message.is_read = True
    db.session.commit()
    
    return {"message": "تم تحديد الرسالة كمقروءة"}

def send_contact_email(sender_name, sender_email, message):
    """Send contact form email to admin"""
    # This is a simplified version - in production use proper email service
    recipient_email = "al66m007@gmail.com"
    
    subject = f"رسالة جديدة من منصة التحكيم - {sender_name}"
    body = f"""
    رسالة جديدة من منصة التحكيم
    
    الاسم: {sender_name}
    البريد الإلكتروني: {sender_email}
    
    الرسالة:
    {message}
    
    تم الإرسال من منصة التحكيم
    """
    
    # Note: This is a placeholder - in production, use proper email service like SendGrid, AWS SES, etc.
    print(f"Email would be sent to {recipient_email}")
    print(f"Subject: {subject}")
    print(f"Body: {body}")


@user_bp.route('/users', methods=['GET'])
def get_users():
    """جلب قائمة المستخدمين (للآدمن فقط)"""
    if 'user_id' not in session:
        return jsonify({'error': 'غير مصرح بالوصول'}), 401
    
    user = User.query.get(session['user_id'])
    if user.user_type != 'admin':
        return jsonify({'error': 'صلاحيات غير كافية'}), 403
    
    users = User.query.all()
    users_data = []
    
    for user in users:
        users_data.append({
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'user_type': user.user_type,
            'created_at': user.created_at.isoformat() if user.created_at else None
        })
    
    return jsonify(users_data)

@user_bp.route('/create-user', methods=['POST'])
def create_user():
    """إنشاء مستخدم جديد (للآدمن فقط)"""
    if 'user_id' not in session:
        return jsonify({'error': 'غير مصرح بالوصول'}), 401
    
    user = User.query.get(session['user_id'])
    if user.user_type != 'admin':
        return jsonify({'error': 'صلاحيات غير كافية'}), 403
    
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    email = data.get('email')
    user_type = data.get('user_type', 'reviewer')
    
    if not username or not password:
        return jsonify({'error': 'اسم المستخدم وكلمة المرور مطلوبان'}), 400
    
    # التحقق من عدم وجود المستخدم
    existing_user = User.query.filter_by(username=username).first()
    if existing_user:
        return jsonify({'error': 'اسم المستخدم موجود بالفعل'}), 400
    
    # إنشاء المستخدم الجديد
    new_user = User(username=username, email=email, user_type=user_type)
    new_user.set_password(password)
    
    db.session.add(new_user)
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'تم إنشاء المستخدم بنجاح'})

@user_bp.route('/delete-user/<int:user_id>', methods=['DELETE'])
def delete_user(user_id):
    """حذف مستخدم (للآدمن فقط)"""
    if 'user_id' not in session:
        return jsonify({'error': 'غير مصرح بالوصول'}), 401
    
    current_user = User.query.get(session['user_id'])
    if current_user.user_type != 'admin':
        return jsonify({'error': 'صلاحيات غير كافية'}), 403
    
    # منع الآدمن من حذف نفسه
    if user_id == session['user_id']:
        return jsonify({'error': 'لا يمكنك حذف حسابك الخاص'}), 400
    
    user_to_delete = User.query.get(user_id)
    if not user_to_delete:
        return jsonify({'error': 'المستخدم غير موجود'}), 404
    
    db.session.delete(user_to_delete)
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'تم حذف المستخدم بنجاح'})

