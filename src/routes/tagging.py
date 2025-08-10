from flask import Blueprint, request, jsonify, session
from werkzeug.utils import secure_filename
import os
import json
import pandas as pd
from datetime import datetime
from src.models.tagging import db, TaggingData, TaggingReview, UploadSession, get_arabic_tag
from src.models.user import User

tagging_bp = Blueprint('tagging', __name__)

UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'xlsx', 'xls'}  # إكسل فقط

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ============
# Excel parser
# ============
def parse_excel_specific(file_path):
    """
    يعالج ملفات إكسل بالقالب التالي (مثل tags_bilingual.xlsx):
      - Paragraph            => النص
      - Ideological_EN/AR
      - Syntactic_EN/AR
      - Functional_EN/AR
      - Discourse_EN/AR
    ينتج قائمة عناصر كل عنصر فيه: text, original_tags(json str), tag_en, tag_ar
    """
    df = pd.read_excel(file_path)

    # أعمدة مطلوبة بالاسم تماماً (حسب القالب)
    required_any_text = ['Paragraph', 'text']  # نسمح بـ Paragraph أو text
    text_col = None
    for name in required_any_text:
        if name in df.columns:
            text_col = name
            break
    if not text_col:
        raise Exception("ملف الإكسل يجب أن يحتوي عمود Paragraph أو text للنص.")

    # أعمدة التصنيفات (وجودها اختياري لكن إن وجدت تُضمّن)
    tag_columns = [
        'Ideological_EN', 'Ideological_AR',
        'Syntactic_EN', 'Syntactic_AR',
        'Functional_EN', 'Functional_AR',
        'Discourse_EN', 'Discourse_AR'
    ]

    processed = []
    for _, row in df.iterrows():
        text = (str(row[text_col]).strip() if pd.notna(row[text_col]) else '')
        if not text:
            continue  # تجاهل صفوف بلا نص

        # اجمع الوسوم المتوفرة في dict
        tags = {}
        for col in tag_columns:
            if col in df.columns and pd.notna(row.get(col)):
                val = str(row[col]).strip()
                if val:
                    tags[col] = val

        # اختر وسمًا رئيسيًا (EN/AR) بحسب أول تصنيف متوفر بالترتيب
        tag_en = ''
        tag_ar = ''
        pairs = [
            ('Ideological_EN', 'Ideological_AR'),
            ('Syntactic_EN',   'Syntactic_AR'),
            ('Functional_EN',  'Functional_AR'),
            ('Discourse_EN',   'Discourse_AR')
        ]
        for en_col, ar_col in pairs:
            en_val = tags.get(en_col, '')
            ar_val = tags.get(ar_col, '')
            if en_val or ar_val:
                tag_en = en_val or ''
                tag_ar = ar_val or (get_arabic_tag(en_val) if en_val else '')
                break

        # fallback لو لا يوجد أي تصنيف
        if not tag_en and not tag_ar:
            tag_en = 'Unknown'
            tag_ar = 'غير محدد'

        processed.append({
            'text': text,
            'original_tags': json.dumps(tags, ensure_ascii=False) if tags else '{}',
            'tag_en': tag_en[:100],  # قص بسيط للاحتياط
            'tag_ar': tag_ar[:100]
        })

    return processed

# ==============================
# رفع ملف (Excel فقط) وحفظ السجلات
# ==============================
@tagging_bp.route('/upload-csv', methods=['POST'])  # الإندبوينت يبقى كما هو لعدم كسر الواجهة
def upload_csv():
    """رفع ملف Excel فقط (xlsx/xls) وفق القالب المحدد"""
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
            os.makedirs(UPLOAD_FOLDER, exist_ok=True)

            filename = secure_filename(file.filename)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{timestamp}_{filename}"
            file_path = os.path.join(UPLOAD_FOLDER, filename)
            file.save(file_path)

            upload_session = UploadSession(
                filename=filename,
                uploaded_by=user.id,
                status='processing'
            )
            db.session.add(upload_session)
            db.session.commit()

            try:
                # معالجة إكسل فقط
                processed_data = parse_excel_specific(file_path)

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
                # إزالة الملف بعد المعالجة
                try:
                    os.remove(file_path)
                except Exception:
                    pass

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
                try:
                    if os.path.exists(file_path):
                        os.remove(file_path)
                except Exception:
                    pass
                return jsonify({'error': f'خطأ في معالجة الملف: {str(e)}'}), 500

        except Exception as e:
            return jsonify({'error': f'خطأ في رفع الملف: {str(e)}'}), 500

    return jsonify({'error': 'نوع الملف غير مدعوم. يرجى رفع ملف Excel (xlsx/xls)'}), 400

# =========================
# بقية المسارات بدون تغيير
# =========================
@tagging_bp.route('/data', methods=['GET'])
def get_tagging_data():
    if 'user_id' not in session:
        return jsonify({'error': 'غير مصرح بالوصول'}), 401

    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    status = request.args.get('status', 'pending')

    query = TaggingData.query.filter_by(status=status)
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
    if 'user_id' not in session:
        return jsonify({'error': 'غير مصرح بالوصول'}), 401

    user = User.query.get(session['user_id'])
    if user.user_type not in ['admin', 'reviewer']:
        return jsonify({'error': 'صلاحيات غير كافية'}), 403

    data = request.get_json()
    required_fields = ['data_id', 'decision']
    for field in required_fields:
        if field not in data:
            return jsonify({'error': f'الحقل {field} مطلوب'}), 400

    tagging_data = TaggingData.query.get(data['data_id'])
    if not tagging_data:
        return jsonify({'error': 'البيانات غير موجودة'}), 404

    existing_review = TaggingReview.query.filter_by(
        data_id=data['data_id'],
        reviewer_id=user.id
    ).first()
    if existing_review:
        return jsonify({'error': 'تم مراجعة هذا العنصر مسبقاً'}), 400

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

    if data['decision'] == 'approve':
        tagging_data.status = 'approved'
    elif data['decision'] == 'modify':
        tagging_data.tag_en = data.get('new_tag_en', tagging_data.tag_en)
        tagging_data.tag_ar = data.get('new_tag_ar', tagging_data.tag_ar)
        tagging_data.status = 'reviewed'

    db.session.commit()
    return jsonify({'success': True, 'message': 'تم إرسال المراجعة بنجاح', 'review_id': review.id})

@tagging_bp.route('/stats', methods=['GET'])
def get_stats():
    if 'user_id' not in session:
        return jsonify({'error': 'غير مصرح بالوصول'}), 401

    user = User.query.get(session['user_id'])

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
    if 'user_id' not in session:
        return jsonify({'error': 'غير مصرح بالوصول'}), 401

    user = User.query.get(session['user_id'])
    if user.user_type != 'admin':
        return jsonify({'error': 'صلاحيات غير كافية'}), 403

    sessions = UploadSession.query.order_by(UploadSession.uploaded_at.desc()).all()
    return jsonify([session.to_dict() for session in sessions])

@tagging_bp.route('/daily-stats', methods=['GET'])
def get_daily_stats():
    if 'user_id' not in session:
        return jsonify({'error': 'غير مصرح بالوصول'}), 401

    user = User.query.get(session['user_id'])
    if user.user_type != 'admin':
        return jsonify({'error': 'صلاحيات غير كافية'}), 403

    today = datetime.now().date()
    daily_reviews = TaggingReview.query.filter(
        TaggingReview.reviewed_at >= today
    ).count()

    reviews_with_time = TaggingReview.query.filter(
        TaggingReview.time_spent.isnot(None),
        TaggingReview.reviewed_at >= today
    ).all()

    avg_time = 0
    if reviews_with_time:
        total_time = sum(review.time_spent for review in reviews_with_time)
        avg_time = round(total_time / len(reviews_with_time), 1)

    return jsonify({'daily_reviews': daily_reviews, 'avg_review_time': avg_time})

@tagging_bp.route('/reviewer-stats', methods=['GET'])
def get_reviewer_stats():
    if 'user_id' not in session:
        return jsonify({'error': 'غير مصرح بالوصول'}), 401

    user = User.query.get(session['user_id'])
    if user.user_type != 'admin':
        return jsonify({'error': 'صلاحيات غير كافية'}), 403

    reviewers = User.query.filter_by(user_type='reviewer').all()
    reviewer_stats = []
    for reviewer in reviewers:
        total_reviews = TaggingReview.query.filter_by(reviewer_id=reviewer.id).count()
        approved_reviews = TaggingReview.query.filter_by(reviewer_id=reviewer.id, decision='approve').count()
        approval_rate = round((approved_reviews / total_reviews) * 100, 1) if total_reviews > 0 else 0
        reviewer_stats.append({
            'username': reviewer.username,
            'review_count': total_reviews,
            'approval_rate': approval_rate
        })

    reviewer_stats.sort(key=lambda x: x['review_count'], reverse=True)
    return jsonify(reviewer_stats)
