# -*- coding: utf-8 -*-
"""Protected interest HTML plus lazy MOMOTOWN student and administrator APIs.

The original HTML GET stays model-free. Identity and private feedback storage
are imported only when their corresponding API endpoints are requested.
"""
import os

from flask import send_file

from app.interest_quest import interest_quest_bp
from app.utils.student_launch import student_launch_required


@interest_quest_bp.after_request
def private_response(response):
    response.headers['Cache-Control'] = 'private, no-store'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    return response


@interest_quest_bp.route('/')
@student_launch_required('STUDENT_INTEREST_QUEST_ENABLED')
def index():
    """로그인·출시 게이트 뒤에서만 제공하는 단일 HTML."""
    path = os.path.join(os.path.dirname(__file__), 'protected', 'index.html')
    response = send_file(path)
    response.headers['Cache-Control'] = 'private, no-store'
    return response


@interest_quest_bp.route('/context')
@student_launch_required('STUDENT_INTEREST_QUEST_ENABLED')
def context():
    from flask import jsonify
    from flask_wtf.csrf import generate_csrf
    from .backend import identity, FORM_VERSION, COPY_VERSION
    student = identity()
    response = jsonify(mode='student' if student else 'admin_preview',
                       display_name=student.name if student else None,
                       csrf_token=generate_csrf(), form_version=FORM_VERSION,
                       copy_version=COPY_VERSION)
    response.headers['Cache-Control'] = 'private, no-store'
    return response


@interest_quest_bp.route('/attempts', methods=['POST'])
@student_launch_required('STUDENT_INTEREST_QUEST_ENABLED')
def create_attempt():
    from flask import abort, jsonify
    from .backend import identity, body_fields, uuid_value, analyze, FORM_VERSION
    from . import store
    student = identity(student_only=True)
    body = body_fields(('request_id', 'form_version', 'answers'))
    uuid_value(body['request_id'])
    if body['form_version'] != FORM_VERSION: abort(400)
    return jsonify(store.create(student.student_id, body, analyze(body['answers'])))


@interest_quest_bp.route('/attempts/<attempt_id>')
@student_launch_required('STUDENT_INTEREST_QUEST_ENABLED')
def get_attempt(attempt_id):
    from flask import jsonify
    from .backend import identity, uuid_value
    from . import store
    student = identity(student_only=True)
    return jsonify(store.restore(student.student_id, uuid_value(attempt_id)))


@interest_quest_bp.route('/attempts/<attempt_id>/presentation', methods=['POST'])
@student_launch_required('STUDENT_INTEREST_QUEST_ENABLED')
def record_presentation(attempt_id):
    from flask import jsonify
    from .backend import identity, body_fields, uuid_value
    from . import store
    student = identity(student_only=True)
    body = body_fields(('analysis_revision','domain_id','sections'))
    uuid_value(body['analysis_revision'])
    return jsonify(store.presentation(student.student_id, uuid_value(attempt_id), body))


@interest_quest_bp.route('/attempts/<attempt_id>/preference', methods=['POST'])
@student_launch_required('STUDENT_INTEREST_QUEST_ENABLED')
def record_preference(attempt_id):
    from flask import jsonify
    from .backend import identity, body_fields, uuid_value
    from . import store
    student = identity(student_only=True)
    body = body_fields(('request_id','analysis_revision','selected_village_id'))
    uuid_value(body['analysis_revision'])
    uuid_value(body['request_id'])
    return jsonify(store.preference(student.student_id, uuid_value(attempt_id), body))


@interest_quest_bp.route('/feedback.json')
def feedback_json():
    from flask import jsonify
    from .backend import admin_filters
    from . import store
    return jsonify(store.lookup(admin_filters()))


@interest_quest_bp.route('/feedback')
def feedback():
    from flask import render_template
    from .backend import admin_filters
    from . import store
    filters = admin_filters()
    return render_template('interest_quest/feedback.html', result=store.lookup(filters), filters=filters)
