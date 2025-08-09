// متغيرات عامة
let currentPage = 1;
let currentStatus = 'pending';
let reviewStartTime = null;

// تهيئة الصفحة
document.addEventListener('DOMContentLoaded', function() {
    // التحقق من الجلسة
    checkSession();
    
    // تهيئة التبويبات
    initTabs();
    
    // تهيئة رفع الملفات
    initFileUpload();
    
    // تحميل البيانات الأولية
    loadDashboardData();
    loadUsers();
    
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
            if (data.user_type !== 'admin') {
                window.location.href = '/reviewer.html';
                return;
            }
            document.getElementById('adminName').textContent = data.username;
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
        case 'dashboard':
            loadDashboardData();
            break;
        case 'upload':
            // تبويب رفع البيانات لا يحتاج تحميل بيانات إضافية
            break;
        case 'review':
            loadReviewData();
            break;
        case 'users':
            loadUsers();
            break;
        case 'reports':
            loadReports();
            break;
        case 'settings':
            // تبويب الإعدادات لا يحتاج تحميل بيانات إضافية
            break;
    }
}

// تحميل بيانات لوحة المعلومات
function loadDashboardData() {
    fetch('/api/tagging/stats')
        .then(response => response.json())
        .then(data => {
            document.getElementById('totalData').textContent = data.total_data || 0;
            document.getElementById('pendingData').textContent = data.pending_data || 0;
            document.getElementById('reviewedData').textContent = data.reviewed_data || 0;
            document.getElementById('completionRate').textContent = (data.completion_rate || 0) + '%';
            
            loadUploadSessions();
        })
        .catch(error => {
            console.error('خطأ في تحميل الإحصائيات:', error);
        });
}

// تحميل جلسات الرفع
function loadUploadSessions() {
    fetch('/api/tagging/upload-sessions')
        .then(response => response.json())
        .then(sessions => {
            const container = document.getElementById('uploadSessionsList');
            container.innerHTML = '';
            
            if (sessions.length === 0) {
                container.innerHTML = '<p>لا توجد جلسات رفع</p>';
                return;
            }
            
            sessions.slice(0, 5).forEach(session => {
                const sessionElement = document.createElement('div');
                sessionElement.className = 'upload-session-item';
                sessionElement.innerHTML = `
                    <div class="session-info">
                        <h4>${session.filename}</h4>
                        <p>تم رفع ${session.processed_records} من ${session.total_records} سجل</p>
                        <span class="session-status ${session.status}">${getStatusText(session.status)}</span>
                    </div>
                    <div class="session-progress">
                        <div class="progress-bar">
                            <div class="progress-fill" style="width: ${session.progress_percentage}%"></div>
                        </div>
                        <span>${session.progress_percentage}%</span>
                    </div>
                `;
                container.appendChild(sessionElement);
            });
        })
        .catch(error => {
            console.error('خطأ في تحميل جلسات الرفع:', error);
        });
}

// تهيئة رفع الملفات
function initFileUpload() {
    const uploadArea = document.getElementById('uploadArea');
    const fileInput = document.getElementById('csvFile');
    
    // Drag and drop
    uploadArea.addEventListener('dragover', function(e) {
        e.preventDefault();
        uploadArea.classList.add('drag-over');
    });
    
    uploadArea.addEventListener('dragleave', function(e) {
        e.preventDefault();
        uploadArea.classList.remove('drag-over');
    });
    
    uploadArea.addEventListener('drop', function(e) {
        e.preventDefault();
        uploadArea.classList.remove('drag-over');
        
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            handleFileUpload(files[0]);
        }
    });
    
    // File input change
    fileInput.addEventListener('change', function(e) {
        if (e.target.files.length > 0) {
            handleFileUpload(e.target.files[0]);
        }
    });
}

// معالجة رفع الملف
function handleFileUpload(file) {
    if (!file.name.toLowerCase().endsWith('.csv')) {
        showMessage('يرجى اختيار ملف CSV', 'error');
        return;
    }
    
    const formData = new FormData();
    formData.append('file', file);
    
    // إظهار شريط التقدم
    const uploadProgress = document.getElementById('uploadProgress');
    const uploadResult = document.getElementById('uploadResult');
    const progressFill = document.getElementById('progressFill');
    const progressText = document.getElementById('progressText');
    
    uploadProgress.style.display = 'block';
    uploadResult.style.display = 'none';
    progressFill.style.width = '0%';
    progressText.textContent = 'جاري الرفع...';
    
    // محاكاة التقدم
    let progress = 0;
    const progressInterval = setInterval(() => {
        progress += Math.random() * 30;
        if (progress > 90) progress = 90;
        progressFill.style.width = progress + '%';
    }, 500);
    
    fetch('/api/tagging/upload-csv', {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        clearInterval(progressInterval);
        progressFill.style.width = '100%';
        progressText.textContent = 'تم الرفع بنجاح!';
        
        setTimeout(() => {
            uploadProgress.style.display = 'none';
            uploadResult.style.display = 'block';
            
            if (data.success) {
                uploadResult.innerHTML = `
                    <div class="success-message">
                        <i class="fas fa-check-circle"></i>
                        <h3>تم رفع الملف بنجاح!</h3>
                        <p>${data.message}</p>
                        <div class="upload-stats">
                            <span>إجمالي السجلات: ${data.total_records}</span>
                            <span>تم معالجتها: ${data.successful_records}</span>
                            ${data.failed_records > 0 ? `<span>فشلت: ${data.failed_records}</span>` : ''}
                        </div>
                    </div>
                `;
                
                // تحديث الإحصائيات
                loadDashboardData();
            } else {
                uploadResult.innerHTML = `
                    <div class="error-message">
                        <i class="fas fa-exclamation-circle"></i>
                        <h3>فشل في رفع الملف</h3>
                        <p>${data.error}</p>
                    </div>
                `;
            }
        }, 1000);
    })
    .catch(error => {
        clearInterval(progressInterval);
        console.error('خطأ في رفع الملف:', error);
        uploadProgress.style.display = 'none';
        uploadResult.style.display = 'block';
        uploadResult.innerHTML = `
            <div class="error-message">
                <i class="fas fa-exclamation-circle"></i>
                <h3>خطأ في الاتصال</h3>
                <p>تعذر رفع الملف. يرجى المحاولة مرة أخرى.</p>
            </div>
        `;
    });
}

// تحميل بيانات المراجعة
function loadReviewData() {
    const status = document.getElementById('statusFilter').value;
    
    fetch(`/api/tagging/data?page=${currentPage}&status=${status}&per_page=10`)
        .then(response => response.json())
        .then(data => {
            displayReviewData(data);
            updatePagination(data);
        })
        .catch(error => {
            console.error('خطأ في تحميل بيانات المراجعة:', error);
        });
}

// عرض بيانات المراجعة
function displayReviewData(data) {
    const container = document.getElementById('reviewList');
    container.innerHTML = '';
    
    if (data.data.length === 0) {
        container.innerHTML = '<p class="no-data">لا توجد بيانات للعرض</p>';
        return;
    }
    
    data.data.forEach(item => {
        const itemElement = document.createElement('div');
        itemElement.className = 'review-item';
        itemElement.innerHTML = `
            <div class="review-item-content">
                <div class="text-preview">
                    <p>${item.text.substring(0, 150)}${item.text.length > 150 ? '...' : ''}</p>
                </div>
                <div class="tags-preview">
                    <span class="tag tag-en">${item.tag_en}</span>
                    <span class="tag tag-ar">${item.tag_ar}</span>
                </div>
                <div class="item-meta">
                    <span class="status ${item.status}">${getStatusText(item.status)}</span>
                    <span class="review-count">${item.review_count} مراجعة</span>
                </div>
            </div>
            <div class="review-item-actions">
                <button class="review-btn" onclick="openReviewModal(${item.id})">
                    <i class="fas fa-eye"></i>
                    مراجعة
                </button>
            </div>
        `;
        container.appendChild(itemElement);
    });
}

// فتح نافذة المراجعة
function openReviewModal(dataId) {
    fetch(`/api/tagging/data?page=1&per_page=1`)
        .then(response => response.json())
        .then(data => {
            const item = data.data.find(d => d.id === dataId);
            if (item) {
                document.getElementById('reviewDataId').value = item.id;
                document.getElementById('reviewText').textContent = item.text;
                document.getElementById('currentTagEn').textContent = item.tag_en;
                document.getElementById('currentTagAr').textContent = item.tag_ar;
                
                document.getElementById('reviewModal').style.display = 'flex';
                reviewStartTime = Date.now();
            }
        })
        .catch(error => {
            console.error('خطأ في تحميل بيانات المراجعة:', error);
        });
}

// إخفاء نافذة المراجعة
function hideReviewModal() {
    document.getElementById('reviewModal').style.display = 'none';
    document.getElementById('reviewForm').reset();
    document.getElementById('modifySection').style.display = 'none';
}

// تحميل المستخدمين
function loadUsers() {
    fetch('/api/users')
        .then(response => response.json())
        .then(users => {
            const tbody = document.getElementById('usersTableBody');
            tbody.innerHTML = '';
            
            users.forEach(user => {
                const row = document.createElement('tr');
                row.innerHTML = `
                    <td>${user.username}</td>
                    <td>${user.user_type === 'admin' ? 'آدمن' : 'محكم'}</td>
                    <td>${user.email || '-'}</td>
                    <td>${formatDate(user.created_at)}</td>
                    <td>
                        ${user.user_type !== 'admin' ? 
                            `<button class="delete-btn" onclick="deleteUser(${user.id})">
                                <i class="fas fa-trash"></i>
                            </button>` : 
                            '<span>-</span>'
                        }
                    </td>
                `;
                tbody.appendChild(row);
            });
        })
        .catch(error => {
            console.error('خطأ في تحميل المستخدمين:', error);
        });
}

// إظهار نافذة إضافة مستخدم
function showAddUserModal() {
    document.getElementById('addUserModal').style.display = 'flex';
}

// إخفاء نافذة إضافة مستخدم
function hideAddUserModal() {
    document.getElementById('addUserModal').style.display = 'none';
    document.getElementById('addUserForm').reset();
}

// تهيئة النماذج
function initForms() {
    // نموذج إضافة مستخدم
    document.getElementById('addUserForm').addEventListener('submit', function(e) {
        e.preventDefault();
        
        const formData = new FormData(this);
        const userData = {
            username: formData.get('username'),
            password: formData.get('password'),
            email: formData.get('email'),
            user_type: 'reviewer'
        };
        
        fetch('/api/create-user', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(userData)
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showMessage('تم إنشاء المستخدم بنجاح', 'success');
                hideAddUserModal();
                loadUsers();
            } else {
                showMessage(data.error, 'error');
            }
        })
        .catch(error => {
            console.error('خطأ في إنشاء المستخدم:', error);
            showMessage('خطأ في الاتصال', 'error');
        });
    });
    
    // نموذج المراجعة
    document.getElementById('reviewForm').addEventListener('submit', function(e) {
        e.preventDefault();
        submitReview();
    });
    
    // تغيير قرار المراجعة
    document.querySelectorAll('input[name="decision"]').forEach(radio => {
        radio.addEventListener('change', function() {
            const modifySection = document.getElementById('modifySection');
            if (this.value === 'modify') {
                modifySection.style.display = 'block';
            } else {
                modifySection.style.display = 'none';
            }
        });
    });
    
    // شريط الثقة
    document.getElementById('confidence').addEventListener('input', function() {
        document.getElementById('confidenceValue').textContent = this.value;
    });
}

// إرسال المراجعة
function submitReview() {
    const formData = new FormData(document.getElementById('reviewForm'));
    const reviewData = {
        data_id: parseInt(formData.get('data_id')),
        decision: formData.get('decision'),
        new_tag_en: formData.get('new_tag_en'),
        new_tag_ar: formData.get('new_tag_ar'),
        notes: formData.get('notes'),
        confidence: parseInt(formData.get('confidence')),
        time_spent: reviewStartTime ? Math.floor((Date.now() - reviewStartTime) / 1000) : null
    };
    
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
            hideReviewModal();
            loadReviewData();
            loadDashboardData();
        } else {
            showMessage(data.error, 'error');
        }
    })
    .catch(error => {
        console.error('خطأ في إرسال المراجعة:', error);
        showMessage('خطأ في الاتصال', 'error');
    });
}

// حذف مستخدم
function deleteUser(userId) {
    if (confirm('هل أنت متأكد من حذف هذا المستخدم؟')) {
        fetch(`/api/delete-user/${userId}`, {
            method: 'DELETE'
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showMessage('تم حذف المستخدم بنجاح', 'success');
                loadUsers();
            } else {
                showMessage(data.error, 'error');
            }
        })
        .catch(error => {
            console.error('خطأ في حذف المستخدم:', error);
            showMessage('خطأ في الاتصال', 'error');
        });
    }
}

// تحميل التقارير
function loadReports() {
    // سيتم تطويرها لاحقاً
    console.log('تحميل التقارير...');
}

// تهيئة اختصارات لوحة المفاتيح
function initKeyboardShortcuts() {
    document.addEventListener('keydown', function(e) {
        // تجاهل الاختصارات إذا كان المستخدم يكتب في حقل
        if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
            return;
        }
        
        switch(e.key.toLowerCase()) {
            case 'a':
                if (document.getElementById('reviewModal').style.display === 'flex') {
                    document.querySelector('input[value="approve"]').checked = true;
                    e.preventDefault();
                }
                break;
            case 'm':
                if (document.getElementById('reviewModal').style.display === 'flex') {
                    document.querySelector('input[value="modify"]').checked = true;
                    document.getElementById('modifySection').style.display = 'block';
                    e.preventDefault();
                }
                break;
            case 'r':
                if (document.getElementById('reviewModal').style.display === 'flex') {
                    document.querySelector('input[value="reject"]').checked = true;
                    e.preventDefault();
                }
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
function getStatusText(status) {
    const statusMap = {
        'pending': 'في الانتظار',
        'reviewed': 'تم المراجعة',
        'approved': 'تم الاعتماد',
        'processing': 'جاري المعالجة',
        'completed': 'مكتمل',
        'failed': 'فشل'
    };
    return statusMap[status] || status;
}

function formatDate(dateString) {
    if (!dateString) return '-';
    const date = new Date(dateString);
    return date.toLocaleDateString('ar-SA');
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

function updatePagination(data) {
    const container = document.getElementById('reviewPagination');
    container.innerHTML = '';
    
    if (data.pages <= 1) return;
    
    // زر السابق
    if (data.has_prev) {
        const prevBtn = document.createElement('button');
        prevBtn.textContent = 'السابق';
        prevBtn.onclick = () => {
            currentPage--;
            loadReviewData();
        };
        container.appendChild(prevBtn);
    }
    
    // أرقام الصفحات
    for (let i = 1; i <= data.pages; i++) {
        const pageBtn = document.createElement('button');
        pageBtn.textContent = i;
        pageBtn.className = i === currentPage ? 'active' : '';
        pageBtn.onclick = () => {
            currentPage = i;
            loadReviewData();
        };
        container.appendChild(pageBtn);
    }
    
    // زر التالي
    if (data.has_next) {
        const nextBtn = document.createElement('button');
        nextBtn.textContent = 'التالي';
        nextBtn.onclick = () => {
            currentPage++;
            loadReviewData();
        };
        container.appendChild(nextBtn);
    }
}


// تحميل التقارير والإحصائيات
function loadReports() {
    // تحميل إحصائيات الأداء اليومي
    fetch('/api/tagging/daily-stats')
        .then(response => response.json())
        .then(data => {
            document.getElementById('dailyReviews').textContent = data.daily_reviews || 0;
            document.getElementById('avgReviewTime').textContent = (data.avg_review_time || 0) + ' ثانية';
        })
        .catch(error => {
            console.error('خطأ في تحميل الإحصائيات اليومية:', error);
            document.getElementById('dailyReviews').textContent = '0';
            document.getElementById('avgReviewTime').textContent = '0 ثانية';
        });
    
    // تحميل أداء المحكمين
    fetch('/api/tagging/reviewer-stats')
        .then(response => response.json())
        .then(reviewers => {
            const container = document.getElementById('reviewerStatsList');
            container.innerHTML = '';
            
            if (reviewers.length === 0) {
                container.innerHTML = '<p>لا توجد إحصائيات متاحة</p>';
                return;
            }
            
            reviewers.forEach(reviewer => {
                const reviewerElement = document.createElement('div');
                reviewerElement.className = 'reviewer-stat-item';
                reviewerElement.innerHTML = `
                    <div class="reviewer-info">
                        <h4>${reviewer.username}</h4>
                        <p>المراجعات: ${reviewer.review_count}</p>
                        <p>معدل الموافقة: ${reviewer.approval_rate}%</p>
                    </div>
                    <div class="reviewer-performance">
                        <div class="performance-bar">
                            <div class="performance-fill" style="width: ${reviewer.approval_rate}%"></div>
                        </div>
                    </div>
                `;
                container.appendChild(reviewerElement);
            });
        })
        .catch(error => {
            console.error('خطأ في تحميل إحصائيات المحكمين:', error);
            document.getElementById('reviewerStatsList').innerHTML = '<p>خطأ في تحميل البيانات</p>';
        });
}

