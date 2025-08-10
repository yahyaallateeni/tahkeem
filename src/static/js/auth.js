/**
 * auth.js
 * -----------------------------------------------------------------------------
 * - يضمن إرسال الكوكيز (الجلسة) مع كل طلب fetch تلقائياً.
 * - يفرض أن استجابات مسارات الـ API فقط ترجع JSON (ويطبع HTML الخطأ إن وُجد).
 * - يوفّر دوال مساعدة لتسجيل الدخول/الخروج والتحقق من الجلسة.
 * -----------------------------------------------------------------------------
 */

/* اعتراض fetch:
   - نضيف credentials: 'include' دائماً (لتمرير كوكي الجلسة مع HTTPS على Render).
   - نُلزم JSON فقط لمسارات تبدأ بـ /api ... حتى لا نكسر تحميل ملفات ثابتة مثل .html/.css/.js */
(function () {
  const originalFetch = window.fetch;

  window.fetch = function (input, init) {
    init = init || {};
    if (!init.credentials) init.credentials = 'include';

    // استخرج العنوان كـ URL لفحص إن كان المسار API أم لا
    let urlString = typeof input === 'string' ? input : (input && input.url) || '';
    let url;
    try { url = new URL(urlString, window.location.href); } catch { url = { pathname: urlString }; }

    return originalFetch(input, init).then(async (response) => {
      // لا نفرض JSON إلا على مسارات /api حتى لا نؤثر على الملفات الثابتة
      const isApi = /\/api(\/|$)/.test(url.pathname || '');

      if (!isApi) {
        return response; // ملفات ثابتة وغيره تُعاد كما هي
      }

      // لمسارات API نتوقع JSON — لو عاد HTML/نص نوضح ذلك في الكونسول
      try {
        const data = await response.clone().json();
        // نحافظ على حالة HTTP ونلفّ JSON المُحلّل
        return new Response(JSON.stringify(data), {
          status: response.status,
          headers: response.headers
        });
      } catch {
        const text = await response.clone().text();
        console.error("⚠ استجابة غير JSON من API:", response.status, (text || '').slice(0, 600));
        throw new Error(`Server returned non-JSON for ${url.pathname} (status ${response.status})`);
      }
    });
  };
})();

/* دوال مساعدة للطلب من الـ API */

// POST JSON عام يعيد {data, status}
async function apiPostJSON(path, bodyObj) {
  const res = await fetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(bodyObj || {})
  });
  const data = await res.json();
  return { data, status: res.status };
}

// GET JSON عام يعيد {data, status}
async function apiGetJSON(path) {
  const res = await fetch(path, { method: 'GET' });
  const data = await res.json();
  return { data, status: res.status };
}

// POST FormData (مثلاً لرفع CSV) — لا تحدد Content-Type يدوياً!
async function apiPostForm(path, formData) {
  const res = await fetch(path, { method: 'POST', body: formData });
  // بعض النهايات قد لا تعيد JSON هنا — نحاول ون fallback إلى نص
  try {
    const data = await res.clone().json();
    return { data, status: res.status };
  } catch {
    const text = await res.text();
    return { data: { raw: text }, status: res.status };
  }
}

/* دوال المصادقة (تستعملها صفحات الدخول/لوحة الإدارة) */

async function login(username, password) {
  return apiPostJSON('/api/login', { username, password });
}

async function logout() {
  return apiPostJSON('/api/logout', {});
}

async function checkSession() {
  return apiGetJSON('/api/check-session');
}

/* تعريض دوال auth/global للملفات الأخرى */
window.auth = {
  login,
  logout,
  checkSession,
  apiGetJSON,
  apiPostJSON,
  apiPostForm
};
