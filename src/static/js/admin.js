/* =========================
   أدوات عامة للتعامل مع الـ fetch
   ========================= */

// قراءة JSON بأمان حتى لو الخادم رجّع نص HTML عند الخطأ
async function readJsonSafe(res) {
  const ct = res.headers.get('content-type') || '';
  if (ct.includes('application/json')) {
    try { return await res.json(); } catch (_) { /* ignore */ }
  }
  return { error: await res.text() };
}

// طلب JSON مع فحص الأخطاء وتطبيع النتيجة
async function fetchJson(url, opts = {}) {
  const res = await fetch(url, { credentials: 'include', ...opts });
  const data = await readJsonSafe(res);
  if (!res.ok) {
    const msg = data?.error || data?.detail || data?.message || `HTTP ${res.status}`;
    throw new Error(msg);
  }
  return data;
}

/* =========================
   رفع ملفات (Excel فقط)
   ========================= */

async function handleUpload() {
  const input = document.getElementById('csvFile');
  const file = input?.files?.[0];

  if (!file) {
    alert('اختر ملفاً أولاً');
    return;
  }

  // سماح بإكسل فقط
  if (!/\.(xlsx|xls)$/i.test(file.name)) {
    alert('يرجى اختيار ملف Excel بامتداد xlsx أو xls');
    return;
  }

  const fd = new FormData();
  fd.append('file', file);

  try {
    const data = await fetchJson('/api/tagging/upload-csv', {
      method: 'POST',
      body: fd
      // ملاحظة: لا تحدد Content-Type مع FormData
    });

    alert(data?.message || 'تم الرفع بنجاح');
    // حدّث قائمة الجلسات بعد نجاح الرفع
    loadUploadSessions();

  } catch (err) {
    console.error('خطأ في رفع الملف:', err);
    alert('تعذّر الرفع: ' + err.message);
  }
}

/* =========================
   تحميل جلسات الرفع (مع تطبيع)
   ========================= */

async function loadUploadSessions() {
  try {
    const raw = await fetchJson('/api/tagging/upload-sessions');

    // تطبيع الاستجابة إلى مصفوفة دائمًا
    const sessions = Array.isArray(raw)
      ? raw
      : (Array.isArray(raw?.sessions) ? raw.sessions
        : (Array.isArray(raw?.data) ? raw.data : []));

    if (!Array.isArray(sessions)) {
      throw new Error('Unexpected response shape for /upload-sessions');
    }

    const latest = sessions.slice(0, 10);
    renderUploadSessions(latest);

  } catch (err) {
    console.error('خطأ في تحميل جلسات الرفع:', err);
    const box = document.getElementById('uploadSessionsBox');
    if (box) box.textContent = 'تعذّر تحميل جلسات الرفع';
  }
}

// Renderer افتراضي بسيط إن لم يكن لديك Renderer خاص
function renderUploadSessions(list) {
  const box = document.getElementById('uploadSessionsBox');
  if (!box) return;
  if (!Array.isArray(list) || list.length === 0) {
    box.textContent = 'لا توجد جلسات رفع بعد.';
    return;
  }
  box.innerHTML = list.map(s => {
    const name = s.filename || s.name || 'ملف';
    const st = s.status || 'غير معروف';
    const total = s.total_records ?? '-';
    const ok = s.processed_records ?? '-';
    const fail = s.failed_records ?? '-';
    const at = s.uploaded_at || s.created_at || '';
    return `<div class="session-row">
      <div><strong>${name}</strong></div>
      <div>الحالة: ${st}</div>
      <div>إجمالي: ${total} | ناجح: ${ok} | فشل: ${fail}</div>
      <div>${at}</div>
    </div>`;
  }).join('');
}

/* =========================
   لوحات وإحصائيات (آمن ضد الأخطاء)
   ========================= */

async function loadDashboardStats() {
  try {
    const stats = await fetchJson('/api/tagging/stats');
    // عناصر اختيارية؛ لن نكسر الصفحة إن لم توجد
    const id = (x) => document.getElementById(x);

    if (id('totalData'))        id('totalData').textContent        = stats.total_data ?? '0';
    if (id('pendingData'))      id('pendingData').textContent      = stats.pending_data ?? '0';
    if (id('reviewedData'))     id('reviewedData').textContent     = stats.reviewed_data ?? '0';
    if (id('approvedData'))     id('approvedData').textContent     = stats.approved_data ?? '0';
    if (id('completionRate'))   id('completionRate').textContent   = (stats.completion_rate ?? 0) + '%';
  } catch (err) {
    console.error('خطأ في تحميل الإحصائيات العامة:', err);
  }
}

async function loadDailyStats() {
  try {
    const daily = await fetchJson('/api/tagging/daily-stats');
    const id = (x) => document.getElementById(x);

    if (id('dailyReviews'))     id('dailyReviews').textContent     = daily.daily_reviews ?? '0';
    if (id('avgReviewTime'))    id('avgReviewTime').textContent    = (daily.avg_review_time ?? 0) + ' ثانية';
  } catch (err) {
    console.error('خطأ في تحميل الإحصائيات اليومية:', err);
  }
}

async function loadReviewerStats() {
  try {
    const list = await fetchJson('/api/tagging/reviewer-stats');
    const box = document.getElementById('reviewersStatsBox');
    if (!box) return;

    if (!Array.isArray(list) || list.length === 0) {
      box.textContent = 'لا توجد بيانات محكّمين بعد.';
      return;
    }

    box.innerHTML = list.map(r => `
      <div class="reviewer-row">
        <div>${r.username || '-'}</div>
        <div>عدد المراجعات: ${r.review_count ?? 0}</div>
        <div>نسبة القبول: ${(r.approval_rate ?? 0)}%</div>
      </div>
    `).join('');
  } catch (err) {
    console.error('خطأ في تحميل إحصائيات المحكّمين:', err);
  }
}

async function loadUsers() {
  try {
    const raw = await fetchJson('/api/users'); // يتطلب جلسة آدمن
    const users = Array.isArray(raw) ? raw : (Array.isArray(raw?.data) ? raw.data : []);
    const box = document.getElementById('usersBox');
    if (!box) return;

    if (users.length === 0) {
      box.textContent = 'لا يوجد مستخدمون.';
      return;
    }

    box.innerHTML = users.map(u => `
      <div class="user-row">
        <div>${u.username || '-'}</div>
        <div>${u.email || '-'}</div>
        <div>${u.user_type || '-'}</div>
      </div>
    `).join('');
  } catch (err) {
    console.error('خطأ في تحميل المستخدمين:', err);
    const box = document.getElementById('usersBox');
    if (box) box.textContent = 'تعذّر تحميل المستخدمين';
  }
}

/* =========================
   تهيئة الصفحة
   ========================= */

document.addEventListener('DOMContentLoaded', () => {
  // ربط زر الرفع
  document.getElementById('uploadBtn')?.addEventListener('click', (e) => {
    e.preventDefault();
    handleUpload();
  });

  // تحميل البيانات الأولية (لن تكسر الصفحة إن لم توجد العناصر)
  loadDashboardStats();
  loadDailyStats();
  loadReviewerStats();
  loadUsers();
  loadUploadSessions();
});
