from datetime import datetime
import json
from .user import db

class TaggingData(db.Model):
    """نموذج البيانات المرفوعة للتحكيم"""
    __tablename__ = 'tagging_data'
    
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text, nullable=False)  # النص العربي
    original_tags = db.Column(db.Text)  # الوسوم الأصلية (JSON)
    tag_en = db.Column(db.String(200))  # الوسم الإنجليزي
    tag_ar = db.Column(db.String(200))  # الوسم العربي
    status = db.Column(db.String(50), default='pending')  # pending, reviewed, approved
    uploaded_by = db.Column(db.Integer)  # معرف المستخدم الذي رفع البيانات
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # العلاقات - معطلة مؤقتاً
    # reviews = db.relationship('TaggingReview', backref='data_item', lazy=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'text': self.text,
            'tag_en': self.tag_en,
            'tag_ar': self.tag_ar,
            'status': self.status,
            'uploaded_at': self.uploaded_at.isoformat() if self.uploaded_at else None,
            'review_count': 0  # سيتم حسابها لاحقاً
        }

class TaggingReview(db.Model):
    """نموذج مراجعات التحكيم"""
    __tablename__ = 'tagging_reviews'
    
    id = db.Column(db.Integer, primary_key=True)
    data_id = db.Column(db.Integer, nullable=False)  # معرف البيانات
    reviewer_id = db.Column(db.Integer, nullable=False)  # معرف المحكم
    
    # قرار المراجع
    decision = db.Column(db.String(50), nullable=False)  # approve, reject, modify
    new_tag_en = db.Column(db.String(200))  # الوسم الجديد بالإنجليزية (في حالة التعديل)
    new_tag_ar = db.Column(db.String(200))  # الوسم الجديد بالعربية (في حالة التعديل)
    
    # ملاحظات المراجع
    notes = db.Column(db.Text)
    confidence = db.Column(db.Integer, default=5)  # مستوى الثقة من 1-10
    
    # معلومات التوقيت
    reviewed_at = db.Column(db.DateTime, default=datetime.utcnow)
    time_spent = db.Column(db.Integer)  # الوقت المستغرق بالثواني
    
    def to_dict(self):
        return {
            'id': self.id,
            'data_id': self.data_id,
            'reviewer_id': self.reviewer_id,
            'decision': self.decision,
            'new_tag_en': self.new_tag_en,
            'new_tag_ar': self.new_tag_ar,
            'notes': self.notes,
            'confidence': self.confidence,
            'reviewed_at': self.reviewed_at.isoformat() if self.reviewed_at else None,
            'time_spent': self.time_spent
        }

class UploadSession(db.Model):
    """نموذج جلسات الرفع"""
    __tablename__ = 'upload_sessions'
    
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    total_records = db.Column(db.Integer, default=0)
    processed_records = db.Column(db.Integer, default=0)
    failed_records = db.Column(db.Integer, default=0)
    status = db.Column(db.String(50), default='processing')  # processing, completed, failed
    uploaded_by = db.Column(db.Integer)  # معرف المستخدم الذي رفع البيانات
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    error_log = db.Column(db.Text)  # سجل الأخطاء
    
    def to_dict(self):
        return {
            'id': self.id,
            'filename': self.filename,
            'total_records': self.total_records,
            'processed_records': self.processed_records,
            'failed_records': self.failed_records,
            'status': self.status,
            'uploaded_at': self.uploaded_at.isoformat() if self.uploaded_at else None,
            'progress_percentage': round((self.processed_records / self.total_records * 100), 2) if self.total_records > 0 else 0
        }

# قاموس ترجمة الوسوم من الإنجليزية للعربية
TAG_TRANSLATIONS = {
    'ReligiousReference': 'مرجع ديني',
    'SelfRepresentation': 'تمثيل الذات',
    'Negative_Other': 'تشويه الآخر',
    'Call_to_Action': 'دعوة للفعل',
    'Positive_Self': 'تمجيد الذات',
    'Negative_Self': 'انتقاد الذات',
    'Positive_Other': 'مدح الآخر',
    'Neutral': 'محايد',
    'Question': 'سؤال',
    'Statement': 'بيان',
    'Emotional': 'عاطفي',
    'Factual': 'حقائقي',
    'Opinion': 'رأي'
}

def get_arabic_tag(english_tag):
    """ترجمة الوسم من الإنجليزية للعربية"""
    return TAG_TRANSLATIONS.get(english_tag, english_tag)

