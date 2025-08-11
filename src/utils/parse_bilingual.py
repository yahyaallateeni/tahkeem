from __future__ import annotations
import os
from typing import List, Dict, Any
import pandas as pd

# خرائط أسماء الأعمدة المحتملة -> الاسم الموحّد
CANONICAL_MAP = {
    # النص
    "paragraph": "text",
    "النص": "text",
    "text": "text",

    # الأيديولوجي
    "ideological_en": "ideological_en",
    "ideological_ar": "ideological_ar",
    "ideology_en": "ideological_en",
    "ideology_ar": "ideological_ar",
    "الأيديولوجي": "ideological_ar",

    # التركيبي
    "syntactic_en": "syntactic_en",
    "syntactic_ar": "syntactic_ar",
    "syntax_en": "syntactic_en",
    "syntax_ar": "syntactic_ar",
    "التركيبي": "syntactic_ar",

    # الوظيفي
    "functional_en": "functional_en",
    "functional_ar": "functional_ar",
    "function_en": "functional_en",
    "function_ar": "functional_ar",
    "الوظيفي": "functional_ar",

    # الخطابي
    "discourse_en": "discourse_en",
    "discourse_ar": "discourse_ar",
    "الخطابي": "discourse_ar",
}

# رؤوس الأعمدة المتوقعة من ملفك المرفق تحديدًا
EXPECTED_HEADERS = {
    "Paragraph": "text",
    "Ideological_EN": "ideological_en",
    "Ideological_AR": "ideological_ar",
    "Syntactic_EN": "syntactic_en",
    "Syntactic_AR": "syntactic_ar",
    "Functional_EN": "functional_en",
    "Functional_AR": "functional_ar",
    "Discourse_EN": "discourse_en",
    "Discourse_AR": "discourse_ar",
}

CANONICAL_ORDER = [
    "text",
    "ideological_en", "ideological_ar",
    "syntactic_en", "syntactic_ar",
    "functional_en", "functional_ar",
    "discourse_en", "discourse_ar",
]

def _normalize_columns(cols) -> Dict[str, str]:
    """
    يحوّل أسماء الأعمدة الموجودة إلى أسماء موحّدة حسب:
    - EXPECTED_HEADERS (الملف المرفق)
    - CANONICAL_MAP (مرادفات عامة)
    """
    mapping: Dict[str, str] = {}
    for c in cols:
        c_str = str(c).strip()
        # أولاً لو من الملف المرفق
        if c_str in EXPECTED_HEADERS:
            mapping[c_str] = EXPECTED_HEADERS[c_str]
            continue
        # تعميم: حوّل للحروف الصغيرة وأزل الفراغات والـ _
        key = c_str.lower().strip().replace(" ", "_")
        if key in CANONICAL_MAP:
            mapping[c_str] = CANONICAL_MAP[key]
        else:
            # اسم مبسّط محفوظ، في حال أردنا استخدامه لاحقًا
            mapping[c_str] = key
    return mapping

def parse_bilingual_file(file_path: str) -> List[Dict[str, Any]]:
    """
    يقرأ ملف xlsx/xls/csv ويعيد قائمة سجلات قياسية:
    [{
        "text": "...",
        "ideological_en": "...", "ideological_ar": "...",
        "syntactic_en": "...",   "syntactic_ar": "...",
        "functional_en": "...",  "functional_ar": "...",
        "discourse_en": "...",   "discourse_ar": "..."
    }, ...]
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(file_path)

    ext = os.path.splitext(file_path)[1].lower()
    if ext in [".xlsx", ".xls"]:
        try:
            df = pd.read_excel(file_path, dtype=str)
        except ImportError as e:
            raise ImportError("Excel support requires the 'openpyxl' package. Please install it in your venv.") from e
    elif ext == ".csv":
        df = pd.read_csv(file_path, dtype=str)
    else:
        raise ValueError("Unsupported file type. Please upload xlsx/xls/csv.")

    # تنظيف الأعمدة وتطبيع الأسماء
    df.columns = [str(c).strip() for c in df.columns]
    col_map = _normalize_columns(df.columns)
    df = df.rename(columns=col_map)

    # التحقق من وجود عمود النص
    if "text" not in df.columns:
        # محاولة تلقائية لاختيار عمود نصّي
        text_candidate = None
        for c in df.columns:
            try:
                if df[c].astype(str).str.len().mean() > 20:
                    text_candidate = c
                    break
            except Exception:
                continue
        if text_candidate:
            df = df.rename(columns={text_candidate: "text"})
        else:
            raise ValueError("لم يتم العثور على عمود يمثل النص (Paragraph/Text).")

    # استبدال القيم المفقودة بسلاسل فارغة
    df = df.fillna("")

    # ترتيب الأعمدة الموحّدة ثم الإضافية
    keep_cols = [c for c in CANONICAL_ORDER if c in df.columns]
    extra = [c for c in df.columns if c not in keep_cols]
    df = df[keep_cols + extra]

    # تحويل إلى list[dict] مع تقليم المسافات
    records = df.to_dict(orient="records")
    for r in records:
        for k, v in list(r.items()):
            if isinstance(v, str):
                r[k] = v.strip()

    return records
