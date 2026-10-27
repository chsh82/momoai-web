"""Lazy server identity and canonical MOMOTOWN analysis helpers."""
from flask import abort
from flask_login import current_user
FORM_VERSION = '1.0.0-draft1+interest-only-momotown-v02'
COPY_VERSION = 'momotown-festival-v02'

def identity(student_only=False):
    if not current_user.is_authenticated or not current_user.is_active:
        abort(403)
    if current_user.role in ('admin', 'master_admin'):
        if student_only: abort(403)
        return None
    if current_user.role != 'student': abort(403)
    from app.models import Student
    students = Student.query.filter_by(user_id=current_user.get_id()).all()
    if len(students) != 1 or not students[0].name or not students[0].name.strip():
        abort(409, description='Student account link requires operational review.')
    return students[0]


def canonical_form():
    import json
    from pathlib import Path
    text = (Path(__file__).parent/'protected'/'index.html').read_text(encoding='utf-8')
    return json.JSONDecoder().raw_decode(text.split('const FORM=', 1)[1])[0]


def analyze(answers):
    form = canonical_form()
    if not isinstance(answers, list) or len(answers) != 32:
        abort(400)
    counts = {d['id']: 0 for d in form['domains']}
    offered = dict(counts)
    for item, answer in zip(form['items'], answers):
        if not isinstance(answer, str) or len(answer) > 64: abort(400)
        choices = {o['id']: o for o in item['options']}
        if answer not in choices: abort(400)
        for option in item['options']:
            offered[option['domain_id']] += option['weight']
        chosen = choices[answer]
        counts[chosen['domain_id']] += chosen['weight']
    domains = [dict(domain_id=d['id'], selected_count=counts[d['id']],
                    offered_count=offered[d['id']],
                    comparison_units=counts[d['id']] * (210 // offered[d['id']]),
                    display_order=i) for i, d in enumerate(form['domains'])]
    representatives = [d['domain_id'] for d in sorted(domains, key=lambda d:(-d['comparison_units'],d['display_order'])) if d['selected_count'] > 0][:3]
    return dict(domains=domains, representatives=representatives)


def uuid_value(value):
    from uuid import UUID
    if not isinstance(value, str) or len(value) != 36: abort(400)
    try:
        if str(UUID(value)) != value: abort(400)
    except ValueError:
        abort(400)
    return value


def body_fields(fields):
    from flask import request
    from flask_wtf.csrf import validate_csrf
    from wtforms.validators import ValidationError
    if request.content_length is not None and request.content_length > 16384: abort(413)
    try:
        validate_csrf(request.headers.get('X-CSRFToken'))
    except ValidationError:
        abort(400, description='Invalid CSRF token.')
    request.max_content_length = 16384
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or set(data) != set(fields): abort(400)
    return data


def admin_filters():
    from flask import request
    from datetime import date
    if (not current_user.is_authenticated or not current_user.is_active or
            current_user.role not in ('admin','master_admin')): abort(403)
    allowed = {'student','form_version','copy_version','date_from','date_to','status','history','limit','offset'}
    args = request.args
    if set(args)-allowed or any(len(args.getlist(k))!=1 or len(v)>128 for k,v in args.items()): abort(400)
    filters = args.to_dict()
    if filters.get('status','') not in ('','completed','pending') or filters.get('history','0') not in ('0','1'): abort(400)
    try:
        if not 1 <= int(filters.get('limit','100')) <= 200: abort(400)
        if not 0 <= int(filters.get('offset','0')) <= 10000: abort(400)
        for k in ('date_from','date_to'):
            if filters.get(k):
                if date.fromisoformat(filters[k]).isoformat() != filters[k]: abort(400)
    except ValueError:
        abort(400)
    return filters
