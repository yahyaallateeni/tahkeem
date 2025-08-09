// متغيرات عامة
let currentReviewData = null;
let reviewStartTime = null;
let currentPage = 1;

// تهيئة الصفحة
document.addEventListener('DOMContentLoaded', function() {
    // التحقق من الجلسة
    checkSession();
    
    // تهيئة التبويبات
    initTabs();
    
    // تحميل البيانات الأولية
    loadReviewData();
    loadProgress();
    
    // تهيئة النماذج
    initForms();
    
    // تهيئة اختصارات لوحة المفاتيح
    initKeyboardShortcuts();
});

// التحقق من الجلسة
function checkSession() {
    fetch('/api/check-session')
        .then(response => response.json())
        .then(data => {
            if (!data.logged_in) {
                window.location.href = '/';
                return;
            }
            if (data.user_type !== 'reviewer') {
                window.location.href = '/admin.html';
                return;
            }
            document.getElementById('reviewerName').textContent = data.username;
        })
        .catch(error => {
            console.error('خطأ في التحقق من الجلسة:', error);
            window.location.href = '/';
        });
}

// تهيئة التبويبات
function initTabs() {
    const navItems = document.querySelectorAll('.nav-item');
    const tabContents = document.querySelectorAll('.tab-content');
    
    navItems.forEach(item => {
        item.addEventListener('click', function() {
            const tabId = this.getAttribute('data-tab');
            
            // إزالة الفئة النشطة من جميع العناصر
            navItems.forEach(nav => nav.classList.remove('active'));
            tabContents.forEach(tab => tab.classList.remove('active'));
            
            // إضافة الفئة النشطة للعنصر المحدد
            this.classList.add('active');
            document.getElementById(tabId).classList.add('active');
            
            // تحميل البيانات حسب التبويب
            loadTabData(tabId);
        });
    });
}

// تحميل بيانات التبويب
function loadTabData(tabId) {
    switch(tabId) {
        case 'review':
            loadReviewData();
            break;
        case 'progress':
            loadProgress();
            break;
        case 'history':
            loadHistory();
            break;
    }
}

// تحميل بيانات المراجعة
function loadReviewData() {
    const reviewLoading = document.getElementById('reviewLoading');
    const reviewContent = document.getElementById('reviewContent');
    const noData = document.getElementById('noData');
    
    reviewLoading.style.display = 'block';
    reviewContent.style.display = 'none';
    noData.style.display = 'none';
    
    fetch('/api/tagging/data?page=1&per_page=1&status=pending')
        .then(response => response.json())
        .then(data => {
            reviewLoading.style.display = 'none';
            
            if (data.data && data.data.length > 0) {
                currentReviewData = data.data[0];
                displayCurrentReview();
                reviewContent.style.display = 'block';
                
                // تحديث الإحصائيات
                document.getElementById('pendingCount').textContent = data.total || 0;
            } else {
                noData.style.display = 'block';
            }
        })
        .catch(error => {
            console.error('خطأ في تحميل بيانات المراجعة:', error);
            reviewLoading.style.display = 'none';
            showMessage('خطأ في تحميل البيانات', 'error');
        });
}

// عرض المراجعة الحالية
function displayCurrentReview() {
    if (!currentReviewData) return;
    
    document.getElementById('textDisplay').textContent = currentReviewData.text;
    document.getElementById('currentTagEn').textContent = currentReviewData.tag_en;
    document.getElementById('currentTagAr').textContent = currentReviewData.tag_ar;
    document.getElementById('currentDataId').value = currentReviewData.id;
    
    // إعادة تعيين النموذج
    document.getElementById('quickReviewForm').reset();
    document.getElementById('modifyForm').style.display = 'none';
    document.getElementById('confidence').value = 5;
    document.getElementById('confidenceValue').textContent = '5';
    
    // بدء توقيت المراجعة
    reviewStartTime = Date.now();
}

// قرار سريع
function quickDecision(decision) {
    if (!currentReviewData) return;
    
    const reviewData = {
        data_id: currentReviewData.id,
        decision: decision,
        confidence: parseInt(document.getElementById('confidence').value),
        time_spent: reviewStartTime ? Math.floor((Date.now() - reviewStartTime) / 1000) : null
    };
    
    submitReview(reviewData);
}

// إظهار نموذج التعديل
function showModifyForm() {
    const modifyForm = document.getElementById('modifyForm');
    modifyForm.style.display = 'block';
    
    // ملء الحقول بالقيم الحالية
    document.getElementById('newTagEn').value = currentReviewData.tag_en;
    document.getElementById('newTagAr').value = currentReviewData.tag_ar;
}

// إخفاء نموذج التعديل
function hideModifyForm() {
    document.getElementById('modifyForm').style.display = 'none';
}

// إرسال التعديل
function submitModification() {
    const newTagEn = document.getElementById('newTagEn').value.trim();
    const newTagAr = document.getElementById('newTagAr').value.trim();
    const notes = document.getElementById('reviewNotes').value.trim();
    
    if (!newTagEn || !newTagAr) {
        showMessage('يرجى ملء جميع حقول التصنيف', 'error');
        return;
    }
    
    const reviewData = {
        data_id: currentReviewData.id,
        decision: 'modify',
        new_tag_en: newTagEn,
        new_tag_ar: newTagAr,
        notes: notes,
        confidence: parseInt(document.getElementById('confidence').value),
        time_spent: reviewStartTime ? Math.floor((Date.now() - reviewStartTime) / 1000) : null
    };
    
    submitReview(reviewData);
}

// إرسال المراجعة
function submitReview(reviewData) {
    fetch('/api/tagging/review', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(reviewData)
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showMessage('تم إرسال المراجعة بنجاح', 'success');
            loadNextReview();
            updateTodayCount();
        } else {
            showMessage(data.error, 'error');
        }
    })
    .catch(error => {
        console.error('خطأ في إرسال المراجعة:', error);
        showMessage('خطأ في الاتصال', 'error');
    });
}

// تحميل المراجعة التالية
function loadNextReview() {
    loadReviewData();
}

// تخطي المراجعة الحالية
function skipCurrent() {
    loadNextReview();
}

// تحديث عداد اليوم
function updateTodayCount() {
    const currentCount = parseInt(document.getElementById('todayReviews').textContent) || 0;
    document.getElementById('todayReviews').textContent = currentCount + 1;
}

// تحميل التقدم
function loadProgress() {
    fetch('/api/tagging/stats')
        .then(response => response.json())
        .then(data => {
            document.getElementById('totalReviews').textContent = data.user_reviews || 0;
            document.getElementById('approvalRate').textContent = (data.user_approval_rate || 0) + '%';
            document.getElementById('todayProgress').textContent = data.today_reviews || 0;
            
            // متوسط الوقت (سيتم حسابه لاحقاً)
            document.getElementById('avgTime').textContent = '30';
        })
        .catch(error => {
            console.error('خطأ في تحميل التقدم:', error);
        });
}

// تحميل السجل
function loadHistory() {
    const filter = document.getElementById('historyFilter').value;
    
    fetch(`/api/tagging/reviews?filter=${filter}&page=${currentPage}`)
        .then(response => response.json())
        .then(data => {
            displayHistory(data);
        })
        .catch(error => {
            console.error('خطأ في تحميل السجل:', error);
            document.getElementById('historyList').innerHTML = '<p>خطأ في تحميل السجل</p>';
        });
}

// عرض السجل
function displayHistory(data) {
    const container = document.getElementById('historyList');
    container.innerHTML = '';
    
    if (!data || !data.reviews || data.reviews.length === 0) {
        container.innerHTML = '<p class="no-data">لا توجد مراجعات في السجل</p>';
        return;
    }
    
    data.reviews.forEach(review => {
        const reviewElement = document.createElement('div');
        reviewElement.className = 'history-item';
        reviewElement.innerHTML = `
            <div class="history-content">
                <div class="history-text">
                    <p>${review.text ? review.text.substring(0, 100) + '...' : 'نص غير متوفر'}</p>
                </div>
                <div class="history-decision">
                    <span class="decision ${review.decision}">${getDecisionText(review.decision)}</span>
                    ${review.new_tag_en ? `<span class="new-tag">${review.new_tag_en} / ${review.new_tag_ar}</span>` : ''}
                </div>
                <div class="history-meta">
                    <span class="date">${formatDate(review.reviewed_at)}</span>
                    <span class="confidence">ثقة: ${review.confidence}/10</span>
                    ${review.time_spent ? `<span class="time">${review.time_spent}ث</span>` : ''}
                </div>
            </div>
        `;
        container.appendChild(reviewElement);
    });
}

// تهيئة النماذج
function initForms() {
    // نموذج التواصل
    document.getElementById('contactForm').addEventListener('submit', function(e) {
        e.preventDefault();
        
        const formData = new FormData(this);
        const messageData = {
            subject: formData.get('subject'),
            message: formData.get('message'),
            sender_type: 'reviewer'
        };
        
        fetch('/api/contact', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(messageData)
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showMessage('تم إرسال الرسالة بنجاح', 'success');
                this.reset();
            } else {
                showMessage(data.error, 'error');
            }
        })
        .catch(error => {
            console.error('خطأ في إرسال الرسالة:', error);
            showMessage('خطأ في الاتصال', 'error');
        });
    });
    
    // شريط الثقة
    document.getElementById('confidence').addEventListener('input', function() {
        document.getElementById('confidenceValue').textContent = this.value;
    });
}

// تهيئة اختصارات لوحة المفاتيح
function initKeyboardShortcuts() {
    document.addEventListener('keydown', function(e) {
        // تجاهل الاختصارات إذا كان المستخدم يكتب في حقل
        if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
            return;
        }
        
        // التأكد من أن تبويب المراجعة نشط
        if (!document.getElementById('review').classList.contains('active')) {
            return;
        }
        
        switch(e.key.toLowerCase()) {
            case 'a':
                quickDecision('approve');
                e.preventDefault();
                break;
            case 'm':
                showModifyForm();
                e.preventDefault();
                break;
            case 'r':
                quickDecision('reject');
                e.preventDefault();
                break;
            case 'n':
                loadNextReview();
                e.preventDefault();
                break;
            case 's':
                skipCurrent();
                e.preventDefault();
                break;
        }
    });
}

// تسجيل الخروج
function logout() {
    fetch('/api/logout', {
        method: 'POST'
    })
    .then(() => {
        window.location.href = '/';
    })
    .catch(error => {
        console.error('خطأ في تسجيل الخروج:', error);
        window.location.href = '/';
    });
}

// دوال مساعدة
function getDecisionText(decision) {
    const decisionMap = {
        'approve': 'موافقة',
        'modify': 'تعديل',
        'reject': 'رفض'
    };
    return decisionMap[decision] || decision;
}

function formatDate(dateString) {
    if (!dateString) return '-';
    const date = new Date(dateString);
    return date.toLocaleDateString('ar-SA', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
}

function showMessage(message, type) {
    // إنشاء عنصر الرسالة
    const messageElement = document.createElement('div');
    messageElement.className = `message ${type}`;
    messageElement.innerHTML = `
        <i class="fas ${type === 'success' ? 'fa-check-circle' : 'fa-exclamation-circle'}"></i>
        <span>${message}</span>
    `;
    
    // إضافة الرسالة للصفحة
    document.body.appendChild(messageElement);
    
    // إزالة الرسالة بعد 3 ثوان
    setTimeout(() => {
        messageElement.remove();
    }, 3000);
}

