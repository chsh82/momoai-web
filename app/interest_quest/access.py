"""Feature-scoped member launch; never changes other exploration gates."""
from functools import wraps
from flask import abort, current_app
from flask_login import current_user
from app.utils.decorators import requires_role

MEMBER_ROLES = ('student', 'parent', 'teacher', 'staff', 'manager', 'admin', 'master_admin')


def member_launch_required(view):
    @wraps(view)
    @requires_role(*MEMBER_ROLES)
    def guarded(*args, **kwargs):
        if not current_user.is_active or current_user.role not in MEMBER_ROLES:
            abort(403)
        member_release = current_app.config.get('MEMBER_INTEREST_QUEST_ENABLED') is True
        legacy_preview = current_user.role in ('admin', 'master_admin')
        legacy_student = (current_user.role == 'student' and
                          current_app.config.get('STUDENT_INTEREST_QUEST_ENABLED') is True)
        if not (member_release or legacy_preview or legacy_student):
            abort(403)
        return view(*args, **kwargs)
    return guarded
