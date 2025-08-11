from functools import wraps
from flask import session, jsonify


def admin_required(fn):
    """Ensure the current session belongs to an admin user."""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'unauthorized'}), 401
        if (session.get('user_type') or '').lower() != 'admin':
            return jsonify({'error': 'forbidden'}), 403
        return fn(*args, **kwargs)
    return wrapper
