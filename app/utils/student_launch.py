"""Student launch gates. No tier/role-level promotion and no persistence."""
from functools import wraps
from flask import abort, current_app
from flask_login import current_user
from app.utils.decorators import requires_role


def student_launch_required(flag):
    def decorate(view):
        @wraps(view)
        @requires_role('admin', 'student')
        def guarded(*args, **kwargs):
            # Keep the existing admin/master_admin preview semantics.
            if current_user.role in ('admin', 'master_admin'):
                return view(*args, **kwargs)
            if not current_user.is_active or current_app.config.get(flag) is not True:
                abort(403)
            return view(*args, **kwargs)
        return guarded
    return decorate
