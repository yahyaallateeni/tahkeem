// ==========================
// اعتراض fetch لإضافة الكوكيز تلقائياً
// ==========================
const originalFetch = window.fetch;
window.fetch = function (input, init = {}) {
    init.credentials = 'include'; // مهم لتمرير الكوكيز مع الطلبات
    return originalFetch(input, init);
};

// ==========================
// دوال المساعدة
// ==========================
function showMessage(id, text, show = true) {
    const el = document.getElementById(id);
    if (!el) return;
    el.style.display = show ? 'block' : 'none';
    el.textContent = text || '';
}

function redirectToDashboard(userType) {
    if (userType === 'admin') {
        window.location.href = 'admin.html';
    } else {
        window.location.href = 'reviewer.html';
    }
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

            const username = document.getElementById('username').value.trim();
            const password = document.getElementById('password').value.trim();

            try {
                const res = await fetch('/api/login', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ username, password }),
                });

                const data = await res.json();
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
});

// ==========================
// التحقق من الجلسة الحالية
// ==========================
async function checkExistingSession() {
    try {
        const res = await fetch('/api/check-session');
        if (res.ok) {
            const data = await res.json();
            if (data.logged_in) {
                redirectToDashboard(data.user_type);
            }
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
        window.location.href = 'index.html';
    } catch (err) {
        console.error('Logout error:', err);
    }
}
