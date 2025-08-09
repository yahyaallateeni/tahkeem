const API_BASE = '/api';

// Initialize app
document.addEventListener('DOMContentLoaded', function() {
    console.log("منصة التحكيم جاهزة");
    
    // Initialize login form
    initLoginForm();
    
    // Check if user is already logged in
    checkExistingSession();
});

// Initialize login form
function initLoginForm() {
    const loginForm = document.getElementById('loginForm');
    if (loginForm) {
        loginForm.addEventListener('submit', handleLogin);
    }
}

// Check for existing session
async function checkExistingSession() {
    // Only check if we're on the main login page
    if (window.location.pathname !== '/' && window.location.pathname !== '/index.html') {
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE}/check-session`, {
            credentials: 'include'
        });
        
        if (response.ok) {
            const data = await response.json();
            if (data.logged_in) {
                // User is logged in, redirect based on type
                if (data.user_type === 'admin') {
                    window.location.href = '/admin.html';
                } else if (data.user_type === 'reviewer') {
                    window.location.href = '/reviewer.html';
                }
            }
        }
    } catch (error) {
        // User not logged in, stay on login page
        console.log('No existing session');
    }
}

// Handle login form submission
async function handleLogin(event) {
    event.preventDefault();
    
    const username = document.getElementById('username').value;
    const password = document.getElementById('password').value;
    
    if (!username || !password) {
        showErrorMessage('يرجى إدخال اسم المستخدم وكلمة المرور');
        return;
    }
    
    showLoadingMessage(true);
    hideErrorMessage();
    
    try {
        const formData = new FormData();
        formData.append('username', username);
        formData.append('password', password);
        
        const response = await fetch(`${API_BASE}/login`, {
            method: 'POST',
            body: formData,
            credentials: 'include'
        });
        
        const data = await response.json();
        
        if (response.ok && data.success) {
            showLoadingMessage(false);
            
            // Redirect based on user type
            if (data.user_type === 'admin') {
                window.location.href = '/admin.html';
            } else if (data.user_type === 'reviewer') {
                window.location.href = '/reviewer.html';
            } else {
                window.location.href = '/';
            }
        } else {
            showLoadingMessage(false);
            showErrorMessage(data.error || 'خطأ في تسجيل الدخول');
        }
    } catch (error) {
        console.error('Login error:', error);
        showLoadingMessage(false);
        showErrorMessage('خطأ في الاتصال بالخادم');
    }
}

// Show error message
function showErrorMessage(message) {
    const errorEl = document.getElementById('errorMessage');
    if (errorEl) {
        errorEl.textContent = message;
        errorEl.style.display = 'block';
        
        // Hide after 5 seconds
        setTimeout(() => {
            hideErrorMessage();
        }, 5000);
    }
}

// Hide error message
function hideErrorMessage() {
    const errorEl = document.getElementById('errorMessage');
    if (errorEl) {
        errorEl.style.display = 'none';
    }
}

// Show/hide loading message
function showLoadingMessage(show) {
    const loadingEl = document.getElementById('loadingMessage');
    if (loadingEl) {
        loadingEl.style.display = show ? 'block' : 'none';
    }
}

// Toggle password visibility
function togglePassword() {
    const passwordInput = document.getElementById('password');
    const toggleBtn = document.querySelector('.toggle-password i');
    
    if (passwordInput.type === 'password') {
        passwordInput.type = 'text';
        toggleBtn.className = 'fas fa-eye-slash';
    } else {
        passwordInput.type = 'password';
        toggleBtn.className = 'fas fa-eye';
    }
}

