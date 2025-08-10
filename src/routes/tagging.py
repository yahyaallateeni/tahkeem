from flask import Blueprint, request, jsonify, session
from werkzeug.utils import secure_filename
import os
import json
import pandas as pd
from datetime import datetime
from sqlalchemy import func
import traceback

from src.models.tagging import db, TaggingData, TaggingReview, UploadSession, get_arabic_tag
from src.models.user import User

tagging_bp = Blueprint('tagging', __name__)

UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'xlsx', 'xls'}  # Excel فقط

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ============ Excel Parser حسب القالب ============
def parse_excel_specific(file_path):
    """
    يتوقع أعمدة مثل:
      Paragraph / text
      Ideological_EN / Ideological_AR
      Syntactic_EN / Syntactic_AR
      Functional_EN / Functional_AR
      Discourse_EN / Discourse_AR
    """
    df = pd.read_excel(file_path)

    # نص
    text_col = None
    for candidate in ['Paragraph', 'text']:
        if candidate in df.columns:
            text_col = candidate
            break
    if not text_col:
        raise Exception("ملف الإكسل يجب أن يحتوي عمود Paragraph أو text للنص.")

    tag_columns = [
        'Ideological_EN', 'Ideological_AR',
        'Syntactic_EN',   'Syntactic_AR',
        'Functional_EN',  'Functional_AR',
        'Discourse_EN',   'Discourse_AR'
    ]

    processed = []
    for _, row in df.iterrows():
        text = (str(row[text_col]).strip() if pd.notna(row[text_col]) else '')
        if not text:
            continue

        tags = {}
        for col in tag_columns:
            if col in df.columns and pd.notna(row.get(col)):
                val = str(row[col]).strip()
                if val:
                    tags[col] = val

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

        if not tag_en and not tag_ar:
            tag_en = 'Unknown'
            tag_ar = 'غير محدد'

        processed.append({
            'text': text,
            'original_tags': json.dumps(tags, ensure_ascii=False) if tags else '{}',
            'tag_en': (tag_en or '')[:100],
            'tag_ar': (tag_ar or '')[:100]
        })

    return processed

# ========== رفع ملف (Excel فقط) ==========
@tagging_bp.route('/upload-csv', methods=['POST'])  # احتفاظ بالمسار القديم لواجهةك
def upload_csv():
    try:
        if 'user_id' not in session:
            return jsonify({'error': 'unauthorized'}), 401

        user = User.query.get(session['user_id'])
        if not user or (user.user_type or '').lower() != 'admin':
            return jsonify({'error': 'forbidden'}), 403

        if 'file' not in request.files:
            return jsonify({'error': 'لم يتم اختيار ملف'}), 400

        file = request.files['file']
        if not file or file.filename == '':
            return jsonify({'error': 'لم يتم اختيار ملف'}), 400

        if not allowed_file(file.filename):
            return jsonify({'error': 'نوع الملف غير مدعوم. يرجى رفع ملف Excel (xlsx/xls)'}), 400

        os.makedirs(UPLOAD_FOLDER, exist_ok=True)
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{timestamp}_{filename}"
        file_path = os.path.join(UPLOAD_FOLDER, filename)
        file.save(file_path)

        upload_session = UploadSession(filename=filename, uploaded_by=user.id, status='processing')
        db.session.add(upload_session)
        db.session.commit()

        try:
            processed = parse_excel_specific(file_path)

            upload_session.total_records = len(processed)
            successful = 0
            failed = 0
            errors = []

            for i, item in enumerate(processed):
                try:
                    rec = TaggingData(
                        text=item['text'],
                        original_tags=item['original_tags'],
                        tag_en=item['tag_en'],
                        tag_ar=item['tag_ar'],
                        uploaded_by=user.id
                    )
                    db.session.add(rec)
                    successful += 1
                except Exception as e:
                    failed += 1
                    errors.append(f"السطر {i+1}: {str(e)}")

            upload_session.processed_records = successful
            upload_session.failed_records = failed
            upload_session.status = 'completed'
            upload_session.error_log = '\n'.join(errors) if errors else None
            db.session.commit()

            try:
                os.remove(file_path)
            except Exception:
                pass

            return jsonify({
                'success': True,
                'message': f'تم رفع الملف بنجاح. تم معالجة {successful} سجل',
                'session_id': upload_session.id,
                'total_records': len(processed),
                'successful_records': successful,
                'failed_records': failed
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
            return jsonify({'error': 'server_error', 'details': str(e)}), 500

    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': 'server_error', 'details': str(e)}), 500

# ========== جلب بيانات للمراجعة ==========
@tagging_bp.route('/data', methods=['GET'])
def get_tagging_data():
    if 'user_id' not in session:
        return jsonify({'error': 'unauthorized'}), 401

    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    status = request.args.get('status', 'pending')

    query = TaggingData.query.filter_by(status=status)

    user = User.query.get(session['user_id'])
    if (user.user_type or '').lower() == 'reviewer':
        reviewed_ids = db.session.query(TaggingReview.data_id).filter_by(reviewer_id=user.id).subquery()
        query = query.filter(~TaggingData.id.in_(reviewed_ids))

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    return jsonify({
        'data': [{
            'id': d.id, 'text': d.text, 'tag_en': d.tag_en, 'tag_ar': d.tag_ar,
            'status': d.status, 'uploaded_by': d.uploaded_by
        } for d in pagination.items],
        'total': pagination.total,
        'pages': pagination.pages,
        'current_page': page,
        'has_next': pagination.has_next,
        'has_prev': pagination.has_prev
    })

# ========== إرسال مراجعة ==========
@tagging_bp.route('/review', methods=['POST'])
def submit_review():
    if 'user_id' not in session:
        return jsonify({'error': 'unauthorized'}), 401

    user = User.query.get(session['user_id'])
    if (user.user_type or '').lower() not in ['admin', 'reviewer']:
        return jsonify({'error': 'forbidden'}), 403

    data = request.get_json() or {}
    for field in ['data_id', 'decision']:
        if field not in data:
            return jsonify({'error': f'الحقل {field} مطلوب'}), 400

    tagging_data = TaggingData.query.get(data['data_id'])
    if not tagging_data:
        return jsonify({'error': 'البيانات غير موجودة'}), 404

    exists = TaggingReview.query.filter_by(data_id=data['data_id'], reviewer_id=user.id).first()
    if exists:
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

# ========== إحصائيات عامة ==========
@tagging_bp.route('/stats', methods=['GET'])
def get_stats():
    try:
        if 'user_id' not in session:
            return jsonify({'error': 'unauthorized'}), 401

        total_data = db.session.query(func.count(TaggingData.id)).scalar() or 0
        pending_data = db.session.query(func.count(TaggingData.id)).filter(TaggingData.status == 'pending').scalar() or 0
        reviewed_data = db.session.query(func.count(TaggingData.id)).filter(TaggingData.status == 'reviewed').scalar() or 0
        approved_data = db.session.query(func.count(TaggingData.id)).filter(TaggingData.status == 'approved').scalar() or 0

        return jsonify({
            'total_data': total_data,
            'pending_data': pending_data,
            'reviewed_data': reviewed_data,
            'approved_data': approved_data,
            'completion_rate': round(((reviewed_data + approved_data) / total_data * 100), 2) if total_data > 0 else 0
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': 'server_error', 'details': str(e)}), 500

# ========== جلسات الرفع ==========
@tagging_bp.route('/upload-sessions', methods=['GET'])
def get_upload_sessions():
    try:
        if 'user_id' not in session:
            return jsonify({'error': 'unauthorized'}), 401

        user = User.query.get(session['user_id'])
        if not user or (user.user_type or '').lower() != 'admin':
            return jsonify({'error': 'forbidden'}), 403

        sessions = UploadSession.query.order_by(UploadSession.uploaded_at.desc()).all()
        out = []
        for s in sessions:
            out.append({
                'id': getattr(s, 'id', None),
                'filename': getattr(s, 'filename', None),
                'status': getattr(s, 'status', None),
                'total_records': getattr(s, 'total_records', None),
                'processed_records': getattr(s, 'processed_records', None),
                'failed_records': getattr(s, 'failed_records', None),
                'error_log': getattr(s, 'error_log', None),
                'uploaded_at': (s.uploaded_at.isoformat() if getattr(s, 'uploaded_at', None) else None),
            })
        return jsonify(out)
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': 'server_error', 'details': str(e)}), 500

# ========== إحصائيات اليوم ==========
@tagging_bp.route('/daily-stats', methods=['GET'])
def get_daily_stats():
    try:
        if 'user_id' not in session:
            return jsonify({'error': 'unauthorized'}), 401

        user = User.query.get(session['user_id'])
        if not user or (user.user_type or '').lower() != 'admin':
            return jsonify({'error': 'forbidden'}), 403

        today = datetime.now().date()
        daily_reviews = db.session.query(func.count(TaggingReview.id))\
            .filter(TaggingReview.reviewed_at >= today).scalar() or 0

        reviews_with_time = TaggingReview.query\
            .filter(TaggingReview.time_spent.isnot(None), TaggingReview.reviewed_at >= today).all()

        if reviews_with_time:
            total_time = sum((getattr(r, 'time_spent', 0) or 0) for r in reviews_with_time)
            avg_time = round(total_time / len(reviews_with_time), 1) if len(reviews_with_time) else 0
        else:
            avg_time = 0

        return jsonify({'daily_reviews': daily_reviews, 'avg_review_time': avg_time})
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': 'server_error', 'details': str(e)}), 500

# ========== إحصائيات المحكّمين ==========
@tagging_bp.route('/reviewer-stats', methods=['GET'])
def get_reviewer_stats():
    try:
        if 'user_id' not in session:
            return jsonify({'error': 'unauthorized'}), 401

        user = User.query.get(session['user_id'])
        if not user or (user.user_type or '').lower() != 'admin':
            return jsonify({'error': 'forbidden'}), 403

        reviewers = User.query.filter_by(user_type='reviewer').all()
        out = []
        for r in reviewers:
            rid = getattr(r, 'id', None)
            total = db.session.query(func.count(TaggingReview.id))\
                .filter(TaggingReview.reviewer_id == rid).scalar() or 0
            ok = db.session.query(func.count(TaggingReview.id))\
                .filter(TaggingReview.reviewer_id == rid, TaggingReview.decision == 'approve').scalar() or 0
            rate = round((ok / total) * 100, 1) if total > 0 else 0
            out.append({'username': getattr(r, 'username', None), 'review_count': total, 'approval_rate': rate})

        out.sort(key=lambda x: x['review_count'], reverse=True)
        return jsonify(out)
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': 'server_error', 'details': str(e)}), 500
