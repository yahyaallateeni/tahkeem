from flask import Blueprint, request, jsonify, session
from werkzeug.utils import secure_filename
import os
import csv
import json
import chardet
from datetime import datetime
from src.models.tagging import db, TaggingData, TaggingReview, UploadSession, get_arabic_tag
from src.models.user import User

tagging_bp = Blueprint('tagging', __name__)

UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'csv'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def detect_encoding(file_path):
    """كشف ترميز الملف"""
    with open(file_path, 'rb') as f:
        raw_data = f.read()
        result = chardet.detect(raw_data)
        return result['encoding']

def parse_original_csv(file_path):
    """معالجة ملف CSV الأصلي"""
    encoding = detect_encoding(file_path)
    
    # جرب ترميزات مختلفة
    encodings_to_try = [encoding, 'utf-8', 'cp1256', 'windows-1256', 'iso-8859-6']
    
    for enc in encodings_to_try:
        try:
            with open(file_path, 'r', encoding=enc, errors='ignore') as f:
                content = f.read()
                
            # تقسيم المحتوى إلى أسطر
            lines = content.strip().split('\n')
            
            processed_data = []
            current_text = ""
            current_tags = ""
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                # تحقق من وجود فاصلة منقوطة (الفاصل الأصلي)
                if ';' in line and not line.startswith('"'):
                    # هذا سطر جديد يحتوي على نص ووسوم
                    if current_text and current_tags:
                        # معالجة السطر السابق
                        processed_data.append(process_text_and_tags(current_text, current_tags))
                    
                    # تقسيم السطر الجديد
                    parts = line.split(';', 1)
                    if len(parts) == 2:
                        current_text = parts[0].strip()
                        current_tags = parts[1].strip()
                    else:
                        current_text = line
                        current_tags = ""
                else:
                    # هذا استكمال للوسوم من السطر السابق
                    current_tags += " " + line
            
            # معالجة آخر عنصر
            if current_text and current_tags:
                processed_data.append(process_text_and_tags(current_text, current_tags))
            
            return processed_data
            
        except Exception as e:
            continue
    
    raise Exception("فشل في قراءة الملف بجميع الترميزات المتاحة")

def process_text_and_tags(text, tags_str):
    """معالجة النص والوسوم"""
    try:
        # تنظيف النص
        text = text.strip('"').strip()
        
        # تنظيف الوسوم
        tags_str = tags_str.strip()
        
        # محاولة تحليل JSON
        if tags_str.startswith('{') and tags_str.endswith('}'):
            try:
                tags_json = json.loads(tags_str)
                # استخراج أول وسم
                first_tag = None
                for key, value in tags_json.items():
                    if isinstance(value, str) and value.strip():
                        first_tag = key
                        break
                
                if first_tag:
                    tag_en = first_tag
                    tag_ar = get_arabic_tag(first_tag)
                else:
                    tag_en = "Unknown"
                    tag_ar = "غير محدد"
                    
            except json.JSONDecodeError:
                tag_en = "ParseError"
                tag_ar = "خطأ في التحليل"
        else:
            # إذا لم تكن JSON، استخدم النص كما هو
            tag_en = tags_str[:100]  # أول 100 حرف
            tag_ar = get_arabic_tag(tag_en)
        
        return {
            'text': text,
            'original_tags': tags_str,
            'tag_en': tag_en,
            'tag_ar': tag_ar
        }
        
    except Exception as e:
        return {
            'text': text,
            'original_tags': tags_str,
            'tag_en': "Error",
            'tag_ar': "خطأ"
        }

@tagging_bp.route('/upload-csv', methods=['POST'])
def upload_csv():
    """رفع ملف CSV"""
    if 'user_id' not in session:
        return jsonify({'error': 'غير مصرح بالوصول'}), 401
    
    user = User.query.get(session['user_id'])
    if not user or user.user_type != 'admin':
        return jsonify({'error': 'صلاحيات غير كافية'}), 403
    
    if 'file' not in request.files:
        return jsonify({'error': 'لم يتم اختيار ملف'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'لم يتم اختيار ملف'}), 400
    
    if file and allowed_file(file.filename):
        try:
            # إنشاء مجلد الرفع إذا لم يكن موجوداً
            os.makedirs(UPLOAD_FOLDER, exist_ok=True)
            
            # حفظ الملف
            filename = secure_filename(file.filename)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{timestamp}_{filename}"
            file_path = os.path.join(UPLOAD_FOLDER, filename)
            file.save(file_path)
            
            # إنشاء جلسة رفع
            upload_session = UploadSession(
                filename=filename,
                uploaded_by=user.id,
                status='processing'
            )
            db.session.add(upload_session)
            db.session.commit()
            
            # معالجة الملف
            try:
                processed_data = parse_original_csv(file_path)
                
                upload_session.total_records = len(processed_data)
                successful_records = 0
                failed_records = 0
                errors = []
                
                for i, data in enumerate(processed_data):
                    try:
                        tagging_data = TaggingData(
                            text=data['text'],
                            original_tags=data['original_tags'],
                            tag_en=data['tag_en'],
                            tag_ar=data['tag_ar'],
                            uploaded_by=user.id
                        )
                        db.session.add(tagging_data)
                        successful_records += 1
                        
                    except Exception as e:
                        failed_records += 1
                        errors.append(f"السطر {i+1}: {str(e)}")
                
                upload_session.processed_records = successful_records
                upload_session.failed_records = failed_records
                upload_session.status = 'completed'
                upload_session.error_log = '\n'.join(errors) if errors else None
                
                db.session.commit()
                
                # حذف الملف المؤقت
                os.remove(file_path)
                
                return jsonify({
                    'success': True,
                    'message': f'تم رفع الملف بنجاح. تم معالجة {successful_records} سجل',
                    'session_id': upload_session.id,
                    'total_records': len(processed_data),
                    'successful_records': successful_records,
                    'failed_records': failed_records
                })
                
            except Exception as e:
                upload_session.status = 'failed'
                upload_session.error_log = str(e)
                db.session.commit()
                
                # حذف الملف المؤقت
                if os.path.exists(file_path):
                    os.remove(file_path)
                
                return jsonify({'error': f'خطأ في معالجة الملف: {str(e)}'}), 500
                
        except Exception as e:
            return jsonify({'error': f'خطأ في رفع الملف: {str(e)}'}), 500
    
    return jsonify({'error': 'نوع الملف غير مدعوم. يرجى رفع ملف CSV'}), 400

@tagging_bp.route('/data', methods=['GET'])
def get_tagging_data():
    """جلب البيانات للمراجعة"""
    if 'user_id' not in session:
        return jsonify({'error': 'غير مصرح بالوصول'}), 401
    
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    status = request.args.get('status', 'pending')
    
    query = TaggingData.query.filter_by(status=status)
    
    # للمحكمين: عرض البيانات التي لم يراجعوها بعد
    user = User.query.get(session['user_id'])
    if user.user_type == 'reviewer':
        reviewed_ids = db.session.query(TaggingReview.data_id).filter_by(reviewer_id=user.id).subquery()
        query = query.filter(~TaggingData.id.in_(reviewed_ids))
    
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    
    return jsonify({
        'data': [item.to_dict() for item in pagination.items],
        'total': pagination.total,
        'pages': pagination.pages,
        'current_page': page,
        'has_next': pagination.has_next,
        'has_prev': pagination.has_prev
    })

@tagging_bp.route('/review', methods=['POST'])
def submit_review():
    """إرسال مراجعة"""
    if 'user_id' not in session:
        return jsonify({'error': 'غير مصرح بالوصول'}), 401
    
    user = User.query.get(session['user_id'])
    if user.user_type not in ['admin', 'reviewer']:
        return jsonify({'error': 'صلاحيات غير كافية'}), 403
    
    data = request.get_json()
    
    # التحقق من البيانات المطلوبة
    required_fields = ['data_id', 'decision']
    for field in required_fields:
        if field not in data:
            return jsonify({'error': f'الحقل {field} مطلوب'}), 400
    
    # التحقق من وجود البيانات
    tagging_data = TaggingData.query.get(data['data_id'])
    if not tagging_data:
        return jsonify({'error': 'البيانات غير موجودة'}), 404
    
    # التحقق من عدم وجود مراجعة سابقة من نفس المستخدم
    existing_review = TaggingReview.query.filter_by(
        data_id=data['data_id'],
        reviewer_id=user.id
    ).first()
    
    if existing_review:
        return jsonify({'error': 'تم مراجعة هذا العنصر مسبقاً'}), 400
    
    # إنشاء المراجعة
    review = TaggingReview(
        data_id=data['data_id'],
        reviewer_id=user.id,
        decision=data['decision'],
        new_tag_en=data.get('new_tag_en'),
        new_tag_ar=data.get('new_tag_ar'),
        notes=data.get('notes'),
        confidence=data.get('confidence', 5),
        time_spent=data.get('time_spent')
    )
    
    db.session.add(review)
    
    # تحديث حالة البيانات إذا كانت موافقة
    if data['decision'] == 'approve':
        tagging_data.status = 'approved'
    elif data['decision'] == 'modify':
        tagging_data.tag_en = data.get('new_tag_en', tagging_data.tag_en)
        tagging_data.tag_ar = data.get('new_tag_ar', tagging_data.tag_ar)
        tagging_data.status = 'reviewed'
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': 'تم إرسال المراجعة بنجاح',
        'review_id': review.id
    })

@tagging_bp.route('/stats', methods=['GET'])
def get_stats():
    """إحصائيات التحكيم"""
    if 'user_id' not in session:
        return jsonify({'error': 'غير مصرح بالوصول'}), 401
    
    user = User.query.get(session['user_id'])
    
    # إحصائيات عامة
    total_data = TaggingData.query.count()
    pending_data = TaggingData.query.filter_by(status='pending').count()
    reviewed_data = TaggingData.query.filter_by(status='reviewed').count()
    approved_data = TaggingData.query.filter_by(status='approved').count()
    
    stats = {
        'total_data': total_data,
        'pending_data': pending_data,
        'reviewed_data': reviewed_data,
        'approved_data': approved_data,
        'completion_rate': round((reviewed_data + approved_data) / total_data * 100, 2) if total_data > 0 else 0
    }
    
    # إحصائيات شخصية للمحكمين
    if user.user_type == 'reviewer':
        user_reviews = TaggingReview.query.filter_by(reviewer_id=user.id).count()
        user_approvals = TaggingReview.query.filter_by(reviewer_id=user.id, decision='approve').count()
        
        stats.update({
            'user_reviews': user_reviews,
            'user_approvals': user_approvals,
            'user_approval_rate': round(user_approvals / user_reviews * 100, 2) if user_reviews > 0 else 0
        })
    
    return jsonify(stats)

@tagging_bp.route('/upload-sessions', methods=['GET'])
def get_upload_sessions():
    """جلب جلسات الرفع"""
    if 'user_id' not in session:
        return jsonify({'error': 'غير مصرح بالوصول'}), 401
    
    user = User.query.get(session['user_id'])
    if user.user_type != 'admin':
        return jsonify({'error': 'صلاحيات غير كافية'}), 403
    
    sessions = UploadSession.query.order_by(UploadSession.uploaded_at.desc()).all()
    
    return jsonify([session.to_dict() for session in sessions])


@tagging_bp.route('/daily-stats', methods=['GET'])
def get_daily_stats():
    """إحصائيات الأداء اليومي"""
    if 'user_id' not in session:
        return jsonify({'error': 'غير مصرح بالوصول'}), 401
    
    user = User.query.get(session['user_id'])
    if user.user_type != 'admin':
        return jsonify({'error': 'صلاحيات غير كافية'}), 403
    
    # إحصائيات اليوم
    today = datetime.now().date()
    daily_reviews = TaggingReview.query.filter(
        TaggingReview.reviewed_at >= today
    ).count()
    
    # متوسط الوقت للمراجعة
    reviews_with_time = TaggingReview.query.filter(
        TaggingReview.time_spent.isnot(None),
        TaggingReview.reviewed_at >= today
    ).all()
    
    avg_time = 0
    if reviews_with_time:
        total_time = sum(review.time_spent for review in reviews_with_time)
        avg_time = round(total_time / len(reviews_with_time), 1)
    
    return jsonify({
        'daily_reviews': daily_reviews,
        'avg_review_time': avg_time
    })

@tagging_bp.route('/reviewer-stats', methods=['GET'])
def get_reviewer_stats():
    """إحصائيات أداء المحكمين"""
    if 'user_id' not in session:
        return jsonify({'error': 'غير مصرح بالوصول'}), 401
    
    user = User.query.get(session['user_id'])
    if user.user_type != 'admin':
        return jsonify({'error': 'صلاحيات غير كافية'}), 403
    
    # جلب جميع المحكمين
    reviewers = User.query.filter_by(user_type='reviewer').all()
    reviewer_stats = []
    
    for reviewer in reviewers:
        total_reviews = TaggingReview.query.filter_by(reviewer_id=reviewer.id).count()
        approved_reviews = TaggingReview.query.filter_by(
            reviewer_id=reviewer.id, 
            decision='approve'
        ).count()
        
        approval_rate = 0
        if total_reviews > 0:
            approval_rate = round((approved_reviews / total_reviews) * 100, 1)
        
        reviewer_stats.append({
            'username': reviewer.username,
            'review_count': total_reviews,
            'approval_rate': approval_rate
        })
    
    # ترتيب حسب عدد المراجعات
    reviewer_stats.sort(key=lambda x: x['review_count'], reverse=True)
    
    return jsonify(reviewer_stats)

