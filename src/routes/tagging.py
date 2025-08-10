from flask import Blueprint, request, jsonify, session
from werkzeug.utils import secure_filename
import os
import csv
import json
import chardet
import pandas as pd
from datetime import datetime
from src.models.tagging import db, TaggingData, TaggingReview, UploadSession, get_arabic_tag
from src.models.user import User

tagging_bp = Blueprint('tagging', __name__)

UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'csv', 'xlsx', 'xls'}

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
    encodings_to_try = [encoding, 'utf-8', 'cp1256', 'windows-1256', 'iso-8859-6']

    for enc in encodings_to_try:
        try:
            with open(file_path, 'r', encoding=enc, errors='ignore') as f:
                content = f.read()

            lines = content.strip().split('\n')
            processed_data = []
            current_text = ""
            current_tags = ""

            for line in lines:
                line = line.strip()
                if not line:
                    continue

                if ';' in line and not line.startswith('"'):
                    if current_text and current_tags:
                        processed_data.append(process_text_and_tags(current_text, current_tags))
                    parts = line.split(';', 1)
                    if len(parts) == 2:
                        current_text = parts[0].strip()
                        current_tags = parts[1].strip()
                    else:
                        current_text = line
                        current_tags = ""
                else:
                    current_tags += " " + line

            if current_text and current_tags:
                processed_data.append(process_text_and_tags(current_text, current_tags))

            return processed_data

        except Exception:
            continue

    raise Exception("فشل في قراءة الملف بجميع الترميزات المتاحة")

def parse_excel(file_path):
    """معالجة ملف Excel"""
    df = pd.read_excel(file_path)
    processed_data = []

    if 'text' not in df.columns or 'original_tags' not in df.columns:
        raise Exception("ملف Excel يجب أن يحتوي على الأعمدة: text, original_tags")

    for _, row in df.iterrows():
        text = str(row['text']) if not pd.isna(row['text']) else ''
        tags_str = str(row['original_tags']) if not pd.isna(row['original_tags']) else ''
        processed_data.append(process_text_and_tags(text, tags_str))

    return processed_data

def process_text_and_tags(text, tags_str):
    """معالجة النص والوسوم"""
    try:
        text = text.strip('"').strip()
        tags_str = tags_str.strip()

        if tags_str.startswith('{') and tags_str.endswith('}'):
            try:
                tags_json = json.loads(tags_str)
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
            tag_en = tags_str[:100]
            tag_ar = get_arabic_tag(tag_en)

        return {
            'text': text,
            'original_tags': tags_str,
            'tag_en': tag_en,
            'tag_ar': tag_ar
        }

    except Exception:
        return {
            'text': text,
            'original_tags': tags_str,
            'tag_en': "Error",
            'tag_ar': "خطأ"
        }

@tagging_bp.route('/upload-csv', methods=['POST'])
def upload_csv():
    """رفع ملف CSV أو Excel"""
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
                ext = filename.rsplit('.', 1)[1].lower()
                if ext in ['xlsx', 'xls']:
                    processed_data = parse_excel(file_path)
                else:
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
                if os.path.exists(file_path):
                    os.remove(file_path)
                return jsonify({'error': f'خطأ في معالجة الملف: {str(e)}'}), 500

        except Exception as e:
            return jsonify({'error': f'خطأ في رفع الملف: {str(e)}'}), 500

    return jsonify({'error': 'نوع الملف غير مدعوم. يرجى رفع ملف CSV أو Excel'}), 400
