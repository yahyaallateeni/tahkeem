// src/static/js/admin.js

// ================ إعداد عام ================
(function patchFetchOnce() {
  if (window.__fetch_patched__) return;
  const orig = window.fetch;
  window.fetch = (u, o = {}) => {
    o.credentials = 'include';
    o.cache = o.cache || 'no-store';
    return orig(u, o);
  };
  window.__fetch_patched__ = true;
})();

const $ = (sel, root) => (root || document).querySelector(sel);
const $$ = (sel, root) => [...(root || document).querySelectorAll(sel)];
const setText = (id, val) => { const el = typeof id === 'string' ? document.getElementById(id) : id; if (el) el.textContent = val ?? ''; };
const show = (el, on) => { if (!el) return; el.style.display = on ? 'block' : 'none'; };

// ================ تنقّل التبويبات ================
function wireTabs() {
  const items = $$('.nav-item');
  items.forEach(li => {
    li.addEventListener('click', () => {
      items.forEach(i => i.classList.remove('active'));
      li.classList.add('active');
      const tab = li.getAttribute('data-tab');
      $$('.tab-content').forEach(t => t.classList.remove('active'));
      const target = document.getElementById(tab);
      if (target) target.classList.add('active');
      if (tab === 'dashboard') { refreshDashboard(); }
      if (tab === 'review')   { loadReviewData(1); }
    });
  });
}

// ================ لوحة المعلومات ================
async function loadStats() {
  try {
    const r = await fetch('/api/tagging/stats');
    if (!r.ok) return;
    const s = await r.json();
    setText('totalData', s.total_data ?? 0);
    setText('pendingData', s.pending_data ?? 0);
    setText('reviewedData', s.reviewed_data ?? 0);
    setText('completionRate', (s.completion_rate ?? 0) + '%');
  } catch (e) { console.warn('stats:', e); }
}

async function loadUploadSessions() {
  try {
    const r = await fetch('/api/tagging/upload-sessions');
    if (!r.ok) return;
    const list = await r.json();
    const box = document.getElementById('uploadSessionsList');
    if (!box) return;
    box.innerHTML = (list.slice(0, 10).map(s => `
      <div class="upload-session-item">
        <div><b>#${s.id}</b> — ${escapeHtml(s.filename || '')}</div>
        <div>الإجمالي: ${s.total_records ?? 0} | ناجح: ${s.processed_records ?? 0} | فشل: ${s.failed_records ?? 0}</div>
        <div>الحالة: ${escapeHtml(s.status || '')} | ${s.uploaded_at ? new Date(s.uploaded_at).toLocaleString('ar') : ''}</div>
        ${s.error_log ? `<pre class="err">${escapeHtml(s.error_log)}</pre>` : ``}
      </div>
    `).join('')) || '<em>لا توجد جلسات</em>';
  } catch (e) { console.warn('upload-sessions:', e); }
}

async function refreshDashboard() {
  await Promise.all([loadStats(), loadUploadSessions()]);
}

// ================ رفع الملف ================
function wireUpload() {
  const input = document.getElementById('csvFile');
  const btn = document.getElementById('uploadBtn');
  const msgEl = document.getElementById('uploadMsg');
  const prog = document.getElementById('uploadProgress');
  const fill = document.getElementById('progressFill');
  const ptxt = document.getElementById('progressText');
  const area = document.getElementById('uploadArea');

  if (!input || !btn) return;

  // تأكد من الإعدادات الصحيحة
  input.name = 'file';
  input.accept = '.xlsx,.xls,.csv';

  const setMsg = (t, ok = true) => { if (!msgEl) return; msgEl.textContent = t || ''; msgEl.style.color = ok ? '#0a0' : '#c00'; };
  const setProgress = (v, text) => { if (fill) fill.style.width = (v || 0) + '%'; if (ptxt) ptxt.textContent = text || ''; };

  // سحب وإفلات
  if (area) {
    ['dragenter', 'dragover'].forEach(ev => area.addEventListener(ev, e => { e.preventDefault(); area.classList.add('dragging'); }));
    ['dragleave', 'drop'].forEach(ev => area.addEventListener(ev, e => { e.preventDefault(); area.classList.remove('dragging'); }));
    area.addEventListener('drop', e => {
      const f = e.dataTransfer?.files?.[0];
      if (f) { input.files = e.dataTransfer.files; setMsg('تم اختيار: ' + f.name, true); }
    });
    area.addEventListener('click', () => input.click());
  }

  input.addEventListener('change', () => {
    const f = input.files?.[0];
    setMsg(f ? ('تم اختيار: ' + f.name) : '', true);
  });

  let inFlight = false;
  btn.addEventListener('click', async () => {
    if (inFlight) return;
    const f = input.files?.[0];
    if (!f) { setMsg('اختر ملفًا أولاً', false); return; }

    const fd = new FormData();
    fd.append('file', f);

    inFlight = true;
    btn.disabled = true;
    show(prog, true);
    setProgress(15, 'بدء الرفع...');
    setMsg('', true);

    try {
      setTimeout(() => setProgress(45, 'جارٍ الرفع...'), 250);
      const res = await fetch('/api/tagging/upload-csv', { method: 'POST', body: fd });
      const txt = await res.text();
      let data; try { data = JSON.parse(txt); } catch {}

      if (res.ok) {
        setProgress(100, 'اكتمل');
        setMsg(`تم: إجمالي=${data?.total_records ?? '-'}، ناجح=${data?.successful_records ?? '-'}، فشل=${data?.failed_records ?? '-'}`, true);
        // تحديث لوحة المعلومات فورًا
        refreshDashboard();
        // تفريغ الاختيار
        input.value = '';
      } else {
        setProgress(0, '');
        setMsg(data?.error || data?.detail || ('خطأ ' + res.status), false);
      }
    } catch (e) {
      console.error(e);
      setProgress(0, '');
      setMsg('خطأ في الاتصال بالخادم', false);
    } finally {
      setTimeout(() => show(prog, false), 900);
      btn.disabled = false;
      inFlight = false;
    }
  });
}

// ================ مراجعة التصنيفات ================
let reviewState = { page: 1, perPage: 10, status: 'pending' };

async function loadReviewData(page) {
  const statusSel = document.getElementById('statusFilter');
  if (statusSel) reviewState.status = statusSel.value || 'pending';
  if (page) reviewState.page = page;

  const listEl = document.getElementById('reviewList');
  const pagEl  = document.getElementById('reviewPagination');
  if (listEl) listEl.innerHTML = '<div class="loading">... جاري التحميل</div>';
  if (pagEl)  pagEl.innerHTML  = '';

  try {
    const url = `/api/tagging/data?status=${encodeURIComponent(reviewState.status)}&page=${reviewState.page}&per_page=${reviewState.perPage}`;
    const r = await fetch(url);
    if (!r.ok) throw new Error('HTTP ' + r.status);
    const data = await r.json();

    // رسم القائمة
    if (listEl) {
      if (!data.data || !data.data.length) {
        listEl.innerHTML = '<div class="empty">لا توجد عناصر</div>';
      } else {
        listEl.innerHTML = data.data.map(item => `
          <div class="review-item">
            <div class="review-text">${escapeHtml(item.text || '')}</div>
            <div class="review-tags">
              <span class="tag tag-en">${escapeHtml(item.tag_en || '')}</span>
              <span class="tag tag-ar">${escapeHtml(item.tag_ar || '')}</span>
            </div>
            <div class="review-actions">
              <button class="save-btn" data-id="${item.id}" data-decision="approve">موافقة</button>
              <button class="save-btn" data-id="${item.id}" data-decision="modify">تعديل</button>
              <button class="cancel-btn" data-id="${item.id}" data-decision="reject">رفض</button>
            </div>
          </div>
        `).join('');
      }
    }

    // ترقيم الصفحات
    if (pagEl) {
      const parts = [];
      const cur = data.current_page || 1;
      const pages = data.pages || 1;

      const btn = (label, p, disabled = false, active = false) =>
        `<button class="page-btn${active ? ' active' : ''}" data-page="${p}" ${disabled ? 'disabled' : ''}>${label}</button>`;

      parts.push(btn('«', Math.max(1, cur - 1), cur <= 1));
      for (let p = Math.max(1, cur - 2); p <= Math.min(pages, cur + 2); p++) {
        parts.push(btn(p, p, false, p === cur));
      }
      parts.push(btn('»', Math.min(pages, cur + 1), cur >= pages));

      pagEl.innerHTML = parts.join('');
      // ربط أزرار الصفحات
      $$('.page-btn', pagEl).forEach(b => {
        b.addEventListener('click', () => {
          const p = parseInt(b.getAttribute('data-page') || '1', 10);
          loadReviewData(p);
        });
      });
    }

    // ربط أزرار المراجعة
    $$('.review-actions .save-btn', listEl).forEach(btn => {
      btn.addEventListener('click', async () => {
        const id = Number(btn.getAttribute('data-id'));
        const decision = btn.getAttribute('data-decision');
        await submitReview(id, decision);
      });
    });

  } catch (e) {
    console.warn('review:', e);
    if (listEl) listEl.innerHTML = '<div class="error">تعذّر تحميل البيانات</div>';
  }
}

async function submitReview(dataId, decision) {
  try {
    const payload = { data_id: dataId, decision };
    const r = await fetch('/api/tagging/review', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    if (!r.ok) {
      const t = await r.text(); throw new Error(t || ('HTTP ' + r.status));
    }
    // تحديث القائمة والإحصائيات
    await Promise.all([loadReviewData(reviewState.page), refreshDashboard()]);
  } catch (e) {
    console.warn('submitReview:', e);
    alert('تعذّر إرسال المراجعة');
  }
}

// ================ المستخدمون (مودال مبسّط) ================
function showAddUserModal() { show(document.getElementById('addUserModal'), true); }
function hideAddUserModal() { show(document.getElementById('addUserModal'), false); }

function wireUsersForm() {
  const form = document.getElementById('addUserForm');
  if (!form) return;
  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const fd = new FormData(form);
    const body = {
      username: fd.get('username'),
      password: fd.get('password'),
      email: fd.get('email')
    };
    try {
      const r = await fetch('/api/admin/users', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
      });
      const t = await r.text();
      if (r.ok) {
        alert('تمت إضافة المحكّم بنجاح');
        hideAddUserModal();
        form.reset();
      } else {
        alert('فشل إضافة المحكّم: ' + t);
      }
    } catch (e2) {
      console.warn(e2);
      alert('خطأ اتصال بالخادم');
    }
  });
}

// ================ خروج ================
async function logout() {
  try {
    await fetch('/api/logout', { method: 'POST' });
  } catch {}
  window.location.href = 'index.html';
}
window.logout = logout;           // كي يعمل من زر الـ sidebar
window.showAddUserModal = showAddUserModal;
window.hideAddUserModal = hideAddUserModal;

// ================ أدوات مساعدة ================
function escapeHtml(s) {
  return String(s || '')
    .replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/>/g, '&gt;').replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

// ================ تشغيل أولي ================
document.addEventListener('DOMContentLoaded', async () => {
  try {
    // تحقق الجلسة السريع (اختياري لعرض اسم الآدمن لاحقًا)
    const cs = await fetch('/api/check-session').then(r => r.ok ? r.json() : null).catch(() => null);
    if (cs?.username) setText('adminName', cs.username);

    wireTabs();
    wireUpload();
    wireUsersForm();
    await refreshDashboard();
    // تحديث تلقائي كل 15 ثانية
    setInterval(refreshDashboard, 15000);

    // حمّل المراجعة لأول مرة إذا تبويبها ظاهر
    if (document.getElementById('review')?.classList.contains('active')) {
      loadReviewData(1);
    }
  } catch (e) {
    console.warn('init:', e);
  }
});
