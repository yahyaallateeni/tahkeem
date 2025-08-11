// ==========================
// اعتراض fetch لإضافة الكوكيز تلقائياً + منع الكاش
// ==========================
(function patchFetchOnce() {
  if (window.__fetch_patched__) return;
  const originalFetch = window.fetch;
  window.fetch = function (input, init = {}) {
    init.credentials = 'include';           // مهم لتمرير الكوكيز مع الطلبات (Secure على HTTPS)
    init.cache = init.cache || 'no-store';  // تقليل مشاكل التخزين المؤقت
    return originalFetch(input, init);
  };
  window.__fetch_patched__ = true;
})();

// ==========================
// دوال المساعدة
// ==========================
function showMessage(id, text, show = true) {
  const el = document.getElementById(id);
  if (!el) return;
  el.style.display = show ? 'block' : 'none';
  el.textContent = text || '';
}

/**
 * توجيه لصفحة لوحة التحكم المناسبة مع "حارس" يمنع إعادة التوجيه لنفس الصفحة
 */
function redirectToDashboard(userType) {
  const target = (userType === 'admin') ? 'admin.html' : 'reviewer.html';
  const here = (window.location.pathname.split('/').pop() || 'index.html').toLowerCase();
  // إذا كنا بالفعل على الصفحة الهدف، لا تفعل شيئًا لتجنب الارتعاش
  if (here === target.toLowerCase()) return;
  window.location.href = target;
}

// ==========================
// تسجيل الدخول
// ==========================
document.addEventListener('DOMContentLoaded', () => {
  const loginForm = document.getElementById('loginForm');
  if (loginForm) {
    loginForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      showMessage('errorMessage', '', false);
      showMessage('loadingMessage', 'جاري تسجيل الدخول...', true);

      const username = document.getElementById('username')?.value.trim();
      const password = document.getElementById('password')?.value.trim();

      try {
        const res = await fetch('/api/login', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ username, password }),
        });

        const data = await res.json().catch(() => ({}));
        if (res.ok) {
          redirectToDashboard(data.user_type);
        } else {
          showMessage('errorMessage', data.detail || 'فشل تسجيل الدخول');
        }
      } catch (err) {
        console.error('Login error:', err);
        showMessage('errorMessage', 'حدث خطأ أثناء الاتصال بالخادم');
      } finally {
        showMessage('loadingMessage', '', false);
      }
    });
  }

  // التحقق من الجلسة الحالية عند تحميل الصفحة
  checkExistingSession();

  // تفعيل زر الرفع إن وُجد في الصفحة (admin.html عادةً)
  wireUploadIfExists();
});

// ==========================
// التحقق من الجلسة الحالية (بدون إعادة تحميل لانهائي)
// ==========================
async function checkExistingSession() {
  try {
    const res = await fetch('/api/check-session', { cache: 'no-store' });
    if (!res.ok) {
      // في حالة 401 لا نعيد تحميل الصفحة؛ فقط نتجاهل ونترك المستخدم يسجل دخول
      return;
    }
    const data = await res.json().catch(() => ({}));
    if (data.logged_in) {
      redirectToDashboard(data.user_type); // التوجيه الآن آمن بسبب الحارس
    }
  } catch (err) {
    console.warn('Session check failed:', err);
  }
}

// ==========================
// تسجيل الخروج
// ==========================
async function logout() {
  try {
    await fetch('/api/logout', { method: 'POST' });
  } catch (err) {
    console.error('Logout error:', err);
  } finally {
    // بعد الخروج، نعود لصفحة الدخول
    const here = (window.location.pathname.split('/').pop() || 'index.html').toLowerCase();
    if (here !== 'index.html') window.location.href = 'index.html';
  }
}

// ==========================
// رفع الملف من الواجهة (اسم الحقل يجب أن يكون "file")
// ==========================
function wireUploadIfExists() {
  const btn = document.getElementById('uploadBtn');
  const input = document.getElementById('csvFile');  // تأكد أن name="file" على الـ <input>
  const msgEl = document.getElementById('uploadMsg');
  if (!btn || !input) return;

  const setMsg = (t, ok = true) => {
    if (!msgEl) return;
    msgEl.textContent = t || '';
    msgEl.style.color = ok ? '#0a0' : '#c00';
  };

  btn.addEventListener('click', async (e) => {
    e.preventDefault?.();

    const f = input.files?.[0];
    if (!f) { setMsg('اختر ملفًا أولاً', false); return; }

    const fd = new FormData();
    fd.append('file', f); // <-- مهم: الاسم الذي ينتظره الباك إند في /api/tagging/upload-csv

    try {
      const res = await fetch('/api/tagging/upload-csv', {
        method: 'POST',
        body: fd
      });
      const txt = await res.text();
      let data; try { data = JSON.parse(txt); } catch {}
      if (res.ok) {
        setMsg(`تم: إجمالي=${data?.total_records ?? '-'}، ناجح=${data?.successful_records ?? '-'}، فشل=${data?.failed_records ?? '-'}`, true);
        console.log('STATUS:', res.status, 'BODY:', txt);
      } else {
        setMsg(data?.error || data?.detail || ('خطأ ' + res.status), false);
        console.warn('STATUS:', res.status, 'BODY:', txt);
      }
    } catch (err) {
      console.error(err);
      setMsg('خطأ في الاتصال بالخادم', false);
    }
  });
}
