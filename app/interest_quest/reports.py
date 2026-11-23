"""Historical result reads: no scorer, DDL, acknowledgement or write connection."""
import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from flask import abort, current_app, jsonify, request, render_template, url_for
from app.interest_quest import interest_quest_bp
from .access import member_launch_required
from .backend import identity, uuid_value
from flask_login import current_user


def account(user_id, role):
    from app.models import User
    rows=User.query.populate_existing().filter_by(user_id=str(user_id),role=role,is_active=True,is_deleted=False).all()
    if len(rows)!=1: abort(403)
    return rows[0]


def report_student():
    account(current_user.get_id(),'student')
    student=identity(student_only=True)
    if student.status!='active': abort(403)
    return student


def linked_children():
    from app.models import ParentStudent, Student, User
    account(current_user.get_id(),'parent')
    return (Student.query.populate_existing()
            .join(ParentStudent,ParentStudent.student_id==Student.student_id)
            .join(User,User.user_id==Student.user_id)
            .filter(ParentStudent.parent_id==current_user.get_id(),ParentStudent.is_active.is_(True),
                    ParentStudent.permission_level.in_(('full','view_only')),Student.status=='active',
                    User.role=='student',User.is_active.is_(True),User.is_deleted.is_(False))
            .order_by(Student.name,Student.student_id).all())


def child(student_id):
    rows=[s for s in linked_children() if s.student_id==student_id]
    if len(rows)!=1: abort(404)
    return rows[0]


@interest_quest_bp.route('/children.json')
@member_launch_required
def children_json():
    return jsonify(children=[dict(student_id=s.student_id,name=s.name) for s in linked_children()])


@interest_quest_bp.route('/children/<student_id>/reports.json')
@member_launch_required
def child_reports_json(student_id):
    return jsonify(history(child(student_id).student_id))


@interest_quest_bp.route('/children/<student_id>/reports/<attempt_id>.json')
@member_launch_required
def child_report_json(student_id,attempt_id):
    return jsonify(historical(child(student_id).student_id,attempt_id))

@contextmanager
def read_connection():
    path=Path(current_app.config.get('MOMOTOWN_FEEDBACK_DB') or Path(current_app.instance_path)/'momotown-feedback.sqlite3')
    db=None
    try:
        if not path.exists():
            yield None
            return
        db=sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True,timeout=0.25)
        db.row_factory=sqlite3.Row
        db.execute('PRAGMA query_only=ON')
        db.execute('BEGIN')
        yield db
    except (sqlite3.Error,OSError):
        abort(503,description='저장 결과를 읽을 수 없어요. 잠시 후 다시 시도해 주세요.')
    finally:
        if db is not None: db.close()

def report_row(db,row):
    snapshot=json.loads(row['snapshot'])
    latest=not db.execute("SELECT 1 FROM attempts WHERE student_id=? AND form_version=? AND origin='STUDENT' AND sequence>? LIMIT 1",(row['student_id'],row['form_version'],row['sequence'])).fetchone()
    return dict(attempt_id=row['attempt_id'],completed_at=row['completed_at'],
                versions={k:row[k] for k in ('form_version','copy_version','scoring_version','representative_rule_version','content_version')},
                latest=latest,response_complete=True,preference_finalized=bool(snapshot.get('preference')),
                snapshot=snapshot,answers=json.loads(row['payload'])['answers'])

def history(student_id):
    try: offset=int(request.args.get('offset','0'))
    except ValueError: abort(400)
    if offset<0 or offset>10000: abort(400)
    with read_connection() as db:
        rows=[] if db is None else db.execute("SELECT * FROM attempts WHERE student_id=? AND origin='STUDENT' ORDER BY sequence DESC LIMIT 21 OFFSET ?",(str(student_id),offset)).fetchall()
        return dict(rows=[report_row(db,r) for r in rows[:20]],has_more=len(rows)>20,offset=offset)

def historical(student_id,attempt_id):
    uuid_value(attempt_id)
    with read_connection() as db:
        row=None if db is None else db.execute("SELECT * FROM attempts WHERE student_id=? AND attempt_id=? AND origin='STUDENT'",(str(student_id),attempt_id)).fetchone()
        if row is None: abort(404)
        return report_row(db,row)

@interest_quest_bp.route('/reports.json')
@member_launch_required
def reports_json():
    return jsonify(history(report_student().student_id))

@interest_quest_bp.route('/reports/<attempt_id>.json')
@member_launch_required
def report_json(attempt_id):
    return jsonify(historical(report_student().student_id,attempt_id))


def catalog_for(record):
    catalog=json.loads((Path(__file__).parent/'report-catalog.json').read_text(encoding='utf-8'))
    return catalog if all(catalog.get(k)==v for k,v in record['versions'].items()) else None


def library_view(student,parent=False):
    result=history(student.student_id)
    return render_template('interest_quest/library.html',student=student,result=result,parent=parent)


def report_view(student,attempt_id,parent=False):
    record=historical(student.student_id,attempt_id)
    return render_template('interest_quest/report.html',student=student,record=record,
                           catalog=catalog_for(record),parent=parent)


@interest_quest_bp.route('/reports')
@member_launch_required
def reports_page():
    return library_view(report_student())


@interest_quest_bp.route('/reports/<attempt_id>')
@interest_quest_bp.route('/reports/<attempt_id>/print')
@member_launch_required
def report_page(attempt_id):
    return report_view(report_student(),attempt_id)


@interest_quest_bp.route('/children')
@member_launch_required
def children_page():
    return render_template('interest_quest/children.html',children=linked_children(),parent=True)


@interest_quest_bp.route('/children/<student_id>/reports')
@member_launch_required
def child_reports_page(student_id):
    return library_view(child(student_id),True)


@interest_quest_bp.route('/children/<student_id>/reports/<attempt_id>')
@interest_quest_bp.route('/children/<student_id>/reports/<attempt_id>/print')
@member_launch_required
def child_report_page(student_id,attempt_id):
    return report_view(child(student_id),attempt_id,True)
