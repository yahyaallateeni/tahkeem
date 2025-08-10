with app.app_context():
    # 1) تأكد من وجود الجداول
    try:
        db.create_all()
    except Exception as e:
        print("DB init error:", e)

    # 2) كبّر عمود password_hash إلى TEXT (أوسع من 120/255) قبل حفظ أي هاش
    try:
        from sqlalchemy import text
        with db.engine.begin() as conn:
            conn.execute(text("ALTER TABLE users ALTER COLUMN password_hash TYPE TEXT"))
        print("password_hash column set to TEXT.")
    except Exception as e:
        # لو كان بالفعل TEXT أو أكبر؛ سيظهر خطأ بسيط ويمكن تجاهله
        print("Skip/ignore password_hash alter (maybe already TEXT):", e)

    # 3) أنشئ/حدّث مستخدم admin وأعد ضبط كلمة المرور دائماً إلى admin123
    try:
        from sqlalchemy import inspect
        cols = set(User.__table__.columns.keys())
        admin = User.query.filter_by(username='admin').first()

        if not admin:
            admin = User(username='admin')
            if 'user_type' in cols:
                admin.user_type = 'admin'
            elif 'role' in cols:
                admin.role = 'admin'
            db.session.add(admin)
            db.session.flush()  # خليه ياخذ ID قبل التعديل

        # أعِد ضبط كلمة المرور باستمرار لضمان التوافق مع check_password
        if hasattr(admin, 'set_password') and callable(getattr(admin, 'set_password')):
            admin.set_password('admin123')
        else:
            # احتياطي نادر جداً
            from werkzeug.security import generate_password_hash
            if 'password_hash' in cols:
                admin.password_hash = generate_password_hash('admin123')
            elif 'password' in cols:
                admin.password = 'admin123'
            else:
                raise RuntimeError("No password field on User model.")

        # تأكيد الدور
        if 'user_type' in cols:
            admin.user_type = 'admin'
        elif 'role' in cols:
            admin.role = 'admin'

        db.session.commit()
        print("Admin ready: username=admin, password=admin123")
    except Exception as e:
        db.session.rollback()
        print("Admin creation/reset error:", e)
