from flask import Blueprint, request, jsonify, session
from src.models.user import User, Sentence, Annotation, ContactMessage, db
from .decorators import admin_required
import csv
import os
import json
import chardet
import io
from werkzeug.utils import secure_filename
from datetime import datetime
import traceback

user_bp = Blueprint('user', __name__)

# ========== المصادقة ==========
@user_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json() if request.is_json else request.form
    username = (data or {}).get('username')
    password = (data or {}).get('password')

    if not username or not password:
        return {"detail": "اسم المستخدم وكلمة المرور مطلوبان"}, 400

    user = User.query.filter_by(username=username).first()
    if not user or not getattr(user, 'check_password', lambda *_: False)(password):
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
    username = (data or {}).get('username')
    password = (data or {}).get('password')
    email = (data or {}).get('email', '')

    if not username or not password:
        return {"detail": "اسم المستخدم وكلمة المرور مطلوبان"}, 400

    existing_user = User.query.filter_by(username=username).first()
    if existing_user:
        return {"detail": "اسم المستخدم موجود بالفعل"}, 400

    user = User(username=username, email=email, user_type="reviewer")
    if hasattr(user, 'set_password') and callable(user.set_password):
        user.set_password(password)
    else:
        return {"detail": "تهيئة كلمة المرور غير متاحة في النموذج"}, 500

    db.session.add(user)
    db.session.commit()
    return {"message": "تم إنشاء الحساب بنجاح"}

# ========== إدارة المستخدمين (للآدمن) ==========
@user_bp.route('/admin/users', methods=['GET'])
@admin_required
def get_all_users_legacy():
    # مسار قديم إن كان مستخدماً في الواجهة
    return get_users()

@user_bp.route('/users', methods=['GET'])
@admin_required
def get_users():
    """جلب قائمة المستخدمين (للآدمن فقط) مع معالجة أخطاء واضحة"""
    try:
        users = User.query.all()
        out = []
        for u in users:
            out.append({
                'id': getattr(u, 'id', None),
                'username': getattr(u, 'username', None),
                'email': getattr(u, 'email', None),
                'user_type': getattr(u, 'user_type', None),
                'created_at': (u.created_at.isoformat() if getattr(u, 'created_at', None) else None)
            })
        return jsonify(out)
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': 'server_error', 'details': str(e)}), 500

@user_bp.route('/admin/users', methods=['POST'])
@admin_required
def create_user_by_admin():
    data = request.get_json() if request.is_json else request.form
    username = (data or {}).get('username')
    password = (data or {}).get('password')
    email = (data or {}).get('email', '')
    user_type = (data or {}).get('user_type', 'reviewer')

    if not username or not password:
        return {"detail": "اسم المستخدم وكلمة المرور مطلوبان"}, 400

    existing_user = User.query.filter_by(username=username).first()
    if existing_user:
        return {"detail": "اسم المستخدم موجود بالفعل"}, 400

    user = User(username=username, email=email, user_type=user_type, created_by=session.get('user_id'))
    if hasattr(user, 'set_password') and callable(user.set_password):
        user.set_password(password)
    else:
        return {"detail": "تهيئة كلمة المرور غير متاحة في النموذج"}, 500

    db.session.add(user)
    db.session.commit()
    return {"message": "تم إنشاء المستخدم بنجاح", "user": {
        'id': user.id, 'username': user.username, 'email': user.email, 'user_type': user.user_type
    }}

@user_bp.route('/admin/users/<user_id>', methods=['DELETE'])
@admin_required
def delete_user_by_admin(user_id):
    user = User.query.get_or_404(user_id)
    if user.id == session.get('user_id'):
        return {"detail": "لا يمكنك حذف حسابك الخاص"}, 400

    db.session.delete(user)
    db.session.commit()
    return {"message": "تم حذف المستخدم بنجاح"}

# ========== رفع CSV القديم (متروك كما هو إن كان مستخدماً) ==========
@user_bp.route('/upload', methods=['POST'])
def upload_csv():
    try:
        if 'file' not in request.files:
            return {"detail": "لم يتم اختيار ملف"}, 400

        file = request.files['file']
        if file.filename == '':
            return {"detail": "لم يتم اختيار ملف"}, 400

        if not file.filename.endswith('.csv'):
            return {"detail": "يجب أن يكون الملف من نوع CSV"}, 400

        stream = file.stream
        stream.seek(0, os.SEEK_END)
        if stream.tell() > 5 * 1024 * 1024:
            return {"detail": "حجم الملف يتجاوز الحد المسموح (5MB)"}, 400
        stream.seek(0)
        sample = stream.read(1024)
        enc = (chardet.detect(sample) or {}).get('encoding') or 'utf-8'
        stream.seek(0)
        text_stream = io.TextIOWrapper(stream, encoding=enc, errors='ignore')
        reader = csv.DictReader(text_stream)

        sentences_added = 0
        for row in reader:
            if 'text' in row:
                s = Sentence(text=row['text'])
                tags = {k: v for k, v in row.items() if k != 'text' and v}
                if tags:
                    s.original_tags_json = json.dumps(tags, ensure_ascii=False)
                db.session.add(s)
                for k, v in tags.items():
                    a = Annotation(sentence=s, tag_key=k, tag_value=v)
                    db.session.add(a)
                sentences_added += 1

        db.session.commit()
        return {"message": f"تم رفع {sentences_added} جملة بنجاح"}
    except Exception as e:
        traceback.print_exc()
        return {"detail": f"خطأ: {str(e)}"}, 400

# ========== المراجعات والإحصائيات / الرسائل ==========
@user_bp.route('/review/pending', methods=['GET'])
def get_pending_reviews():
    pending = Annotation.query.filter_by(is_correct=None).limit(50).all()
    result = []
    for a in pending:
        result.append({
            'annotation': {
                'id': a.id, 'tag_key': a.tag_key, 'tag_value': a.tag_value,
                'is_correct': a.is_correct
            },
            'sentence': {'id': a.sentence.id, 'text': a.sentence.text}
        })
    return jsonify(result)

@user_bp.route('/review/<annotation_id>', methods=['POST'])
def submit_review(annotation_id):
    data = request.get_json() if request.is_json else request.form
    is_correct = (data or {}).get('is_correct')
    comment = (data or {}).get('comment', '')

    annotation = Annotation.query.get_or_404(annotation_id)
    annotation.is_correct = is_correct
    annotation.reviewer_comment = comment
    annotation.reviewer_id = session.get('user_id')
    annotation.reviewed_at = datetime.utcnow()
    db.session.commit()
    return {"message": "تم حفظ المراجعة بنجاح"}

@user_bp.route('/stats', methods=['GET'])
def get_statistics():
    total_sentences = Sentence.query.count()
    total_annotations = Annotation.query.count()
    reviewed_annotations = Annotation.query.filter(Annotation.is_correct.isnot(None)).count()
    pending_annotations = Annotation.query.filter_by(is_correct=None).count()
    return jsonify({
        'total_sentences': total_sentences,
        'total_annotations': total_annotations,
        'reviewed_annotations': reviewed_annotations,
        'pending_annotations': pending_annotations,
        'completion_rate': round((reviewed_annotations / total_annotations * 100) if total_annotations > 0 else 0, 2)
    })

@user_bp.route('/contact', methods=['POST'])
def submit_contact():
    data = request.get_json() if request.is_json else request.form
    sender_name = (data or {}).get('sender_name')
    sender_email = (data or {}).get('sender_email')
    message = (data or {}).get('message')

    if not all([sender_name, sender_email, message]):
        return {"detail": "جميع الحقول مطلوبة"}, 400

    contact_msg = ContactMessage(sender_name=sender_name, sender_email=sender_email, message=message)
    db.session.add(contact_msg)
    db.session.commit()

    # إرسال بريد فعلي غير مُفعّل هنا؛ نطبع فقط
    print(f"[CONTACT] to admin: {sender_name} <{sender_email}> :: {message}")
    return {"message": "تم إرسال رسالتك بنجاح"}

@user_bp.route('/admin/messages', methods=['GET'])
@admin_required
def get_contact_messages():
    messages = ContactMessage.query.order_by(ContactMessage.created_at.desc()).all()
    out = []
    for m in messages:
        out.append({
            'id': m.id, 'sender_name': m.sender_name, 'sender_email': m.sender_email,
            'message': m.message, 'is_read': m.is_read,
            'created_at': (m.created_at.isoformat() if m.created_at else None)
        })
    return jsonify(out)

@user_bp.route('/admin/messages/<message_id>/read', methods=['POST'])
@admin_required
def mark_message_read(message_id):
    message = ContactMessage.query.get_or_404(message_id)
    message.is_read = True
    db.session.commit()
    return {"message": "تم تحديد الرسالة كمقروءة"}
