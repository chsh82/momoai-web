#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""2단계(활동별 적립 훅 연결) 확인 스크립트

docs/mileage/07_개발지시서_2단계.md "확인 스크립트" 5개 항목을 검증한다.
이 프로젝트의 기존 test_*.py 관행대로 pytest가 아니라 create_app() + 직접
쿼리 + print() 방식으로 만들었다(test_mileage_service.py와 동일 패턴).

주의: 3번(QS01) 항목은 community.new() 라우트 자체가 관리자 전용으로 막혀
있어(1번 결정사항) HTTP 라우트를 통해 재현할 수 없다. 훅이 실제로 호출하는
것과 동일한 award_points() 시그니처를 직접 호출해 마일리지 쪽 로직만
검증한다 - 라우트 자체가 도달 불가능하다는 사실은 이미 보고서에서 확인받음.
4~5번도 같은 이유로(Flask 로그인 세션을 스크립트에서 재현하기보다) 라우트가
실행하는 것과 동일한 순서의 로직을 직접 호출해서 검증한다.

테스트용으로 만든 User/Student/Post/Comment/Essay/PointEvent는 스크립트
마지막에 전부 삭제한다.
"""
import sys
import io
from datetime import datetime

if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from app import create_app
from app.models import db
from app.models.user import User
from app.models.student import Student
from app.models.essay import Essay
from app.models.community import Post, Comment
from app.models.mileage import PointEvent
from app.essays.momoai_service import MOMOAIService
from app.services import mileage_service as svc

app = create_app('development')

# 이 테스트는 마일리지 적립 시작일 게이트(2026-09-01, MILEAGE_START_DATE)와
# 무관한 로직을 확인한다. 이 스크립트를 시작일 이전(오늘)에 돌리면 occurred_at
# 기본값(datetime.utcnow())이 게이트에 걸려 모든 적립이 조용히 무시되므로,
# 두 모듈이 각자 import해 간 상수를 테스트 범위 안에서만 과거로 낮춰 우회한다.
import app.services.mileage_service as _mileage_service_mod
import app.services.mileage_batch_service as _mileage_batch_service_mod
from datetime import date as _date
_mileage_service_mod.MILEAGE_START_DATE = _date(2000, 1, 1)
_mileage_batch_service_mod.MILEAGE_START_DATE = _date(2000, 1, 1)

failures = []


def check(label, condition):
    mark = 'PASS' if condition else 'FAIL'
    print(f"  [{mark}] {label}")
    if not condition:
        failures.append(label)


with app.app_context():
    print("=" * 70)
    print("마일리지 훅 연결 확인 스크립트")
    print("=" * 70)

    teacher = User(email='_hooks_test_teacher@example.com', name='_hooks_test_teacher',
                   role='teacher', role_level=3)
    teacher.set_password('test_password_only')
    admin = User(email='_hooks_test_admin@example.com', name='_hooks_test_admin',
                 role='admin', role_level=1)
    admin.set_password('test_password_only')
    student_user = User(email='_hooks_test_student@example.com', name='_hooks_test_student_user',
                        role='student', role_level=5)
    student_user.set_password('test_password_only')
    db.session.add_all([teacher, admin, student_user])
    db.session.flush()

    student = Student(teacher_id=teacher.user_id, user_id=student_user.user_id,
                      name='_hooks_test_student', grade='초5')
    db.session.add(student)
    db.session.flush()
    student_id = student.student_id
    print(f"\n테스트 학생 생성: {student_id} (계정 연결: {student_user.user_id})")

    # 정리 단계에서 만료된 ORM 객체 속성에 접근하지 않도록, ID는 생성 즉시
    # 별도 문자열 변수로 뽑아 둔다(중간에 commit/rollback이 섞여도 안전하게 정리하기 위함).
    essay_id_val = None
    post_id_val = None
    post2_id_val = None
    post3_id_val = None
    comment_id_val = None
    parent_id_val = None
    reply_id_val = None
    parent2_id_val = None
    reply2_id_val = None

    try:
        # 1. 첨삭 확정(리라이팅 유형) -> 학생에게 500점 (강사가 아니라)
        print("\n[1] 첨삭 확정(리라이팅) -> 학생에게 500점이 붙는가 (강사가 아니라)")
        essay = Essay(student_id=student_id, user_id=teacher.user_id,
                      original_text='테스트 원문', grade='초5', status='reviewing',
                      essay_type='rewriting')
        db.session.add(essay)
        db.session.flush()
        essay_id_val = essay.essay_id

        # essays/momoai_service.py의 finalize_essay() 훅을 그대로 호출한다.
        # self를 쓰지 않는 메서드라 인스턴스 생성(API 키/문서 로딩) 없이 바로 호출 가능.
        MOMOAIService.finalize_essay(None, essay)

        student_total = svc.get_total_points(student_id)
        check(f"essay.is_finalized == True (실제: {essay.is_finalized})", essay.is_finalized is True)
        check(f"학생 누적 포인트 500 (실제: {student_total})", student_total == 500)

        student_events_for_teacher_id = PointEvent.query.filter_by(student_id=teacher.user_id).count()
        check(f"강사 user_id로는 포인트가 적립되지 않음 (실제: {student_events_for_teacher_id}건)",
              student_events_for_teacher_id == 0)

        # 2. 같은 첨삭 다시 확정 -> 점수 그대로
        print("\n[2] 같은 첨삭을 다시 확정해도 점수가 늘지 않는가")
        MOMOAIService.finalize_essay(None, essay)
        student_total_after = svc.get_total_points(student_id)
        check(f"재확정 후에도 500점 그대로 (실제: {student_total_after})", student_total_after == 500)

        # 3. 질문 카테고리 글 작성 -> pending 100점
        # community.new()가 admin 전용으로 막혀 있어(1번 결정사항) 라우트를 통한
        # 재현이 불가능함 - 훅이 호출하는 것과 동일한 award_points() 시그니처를 직접 검증.
        print("\n[3] 질문 카테고리 글 작성 -> pending 100점 (QS01, 훅과 동일한 호출을 직접 검증)")
        post = Post(user_id=student_user.user_id, title='테스트 질문',
                   content='테스트 내용', category='question')
        db.session.add(post)
        db.session.flush()
        post_id_val = post.post_id

        qs01_event = svc.award_points(
            student_id=student_id, activity_code='QS01',
            source_type='post', source_id=str(post.post_id),
        )
        check("QS01 적립 성공", qs01_event is not None)
        check(f"상태가 pending (실제: {qs01_event.status if qs01_event else None})",
              qs01_event is not None and qs01_event.status == 'pending')
        check(f"점수 100 (실제: {qs01_event.points if qs01_event else None})",
              qs01_event is not None and qs01_event.points == 100)
        # pending도 누적 포인트에는 반영됨(05_DB설계서 2.1절 - status != 'cancelled'면 합산)
        total_with_pending = svc.get_total_points(student_id)
        check(f"pending 포함 누적 포인트 600 (500+100, 실제: {total_with_pending})",
              total_with_pending == 600)

        # 4. 그 글을 삭제하면 점수가 사라지는가
        # community.delete() 라우트와 동일한 순서(취소 -> 삭제)를 직접 재현.
        print("\n[4] 게시글 삭제 -> QS01 포인트가 취소되는가")
        cancel_count = svc.cancel_points('post', post.post_id, '게시글 삭제')
        check(f"취소 처리 1건 (실제: {cancel_count}건)", cancel_count == 1)
        db.session.delete(post)
        db.session.flush()
        total_after_post_delete = svc.get_total_points(student_id)
        check(f"게시글 삭제 후 누적 포인트가 500으로 복귀 (실제: {total_after_post_delete})",
              total_after_post_delete == 500)

        # 5. 댓글을 삭제하면 소프트 삭제되고 화면 조회에서 빠지는가
        print("\n[5] 댓글 삭제 -> 소프트 삭제 + CM01 취소 + 조회에서 제외")
        post2 = Post(user_id=admin.user_id, title='테스트 게시글2',
                    content='내용', category='free')
        db.session.add(post2)
        db.session.flush()
        post2_id_val = post2.post_id

        comment = Comment(post_id=post2.post_id, user_id=student_user.user_id, content='테스트 댓글')
        db.session.add(comment)
        db.session.flush()
        comment_id_val = comment.comment_id
        cm01_event = svc.award_points(
            student_id=student_id, activity_code='CM01',
            source_type='comment', source_id=str(comment.comment_id),
        )
        check("CM01 적립 성공", cm01_event is not None)
        total_with_cm01 = svc.get_total_points(student_id)
        check(f"CM01 포함 누적 포인트 510 (실제: {total_with_cm01})", total_with_cm01 == 510)

        # community.delete_comment()와 동일한 순서: 소프트 삭제 -> 취소
        comment.is_deleted = True
        comment.deleted_at = datetime.utcnow()
        cm01_cancel_count = svc.cancel_points('comment', comment.comment_id, '댓글 삭제')
        db.session.flush()

        check(f"소프트 삭제됨 (is_deleted={comment.is_deleted})", comment.is_deleted is True)
        check(f"CM01 취소 1건 (실제: {cm01_cancel_count}건)", cm01_cancel_count == 1)
        total_after_comment_delete = svc.get_total_points(student_id)
        check(f"댓글 삭제 후 누적 포인트가 500으로 복귀 (실제: {total_after_comment_delete})",
              total_after_comment_delete == 500)

        # community.detail()의 조회 쿼리와 동일한 필터로 확인
        visible = Comment.query.filter_by(post_id=post2.post_id, parent_comment_id=None,
                                          is_deleted=False).all()
        check(f"detail() 쿼리 조회에서 제외됨 (실제 조회 건수: {len(visible)})", len(visible) == 0)
        # Post.comment_count 프로퍼티도 확인
        check(f"post.comment_count가 삭제된 댓글을 제외함 (실제: {post2.comment_count})",
              post2.comment_count == 0)

        # 6. (회귀 수정 확인) 부모 댓글 삭제 시 대댓글까지 함께 처리되는가
        print("\n[6] 부모 댓글 삭제 -> 대댓글도 소프트 삭제 + CM01 취소되는가 (회귀 수정)")
        post3 = Post(user_id=admin.user_id, title='테스트 게시글3', content='내용', category='free')
        db.session.add(post3)
        db.session.flush()
        post3_id_val = post3.post_id

        parent_c = Comment(post_id=post3.post_id, user_id=student_user.user_id, content='부모 댓글')
        db.session.add(parent_c)
        db.session.flush()
        reply_c = Comment(post_id=post3.post_id, user_id=student_user.user_id, content='대댓글',
                          parent_comment_id=parent_c.comment_id)
        db.session.add(reply_c)
        db.session.flush()
        parent_id_val = parent_c.comment_id
        reply_id_val = reply_c.comment_id

        svc.award_points(student_id=student_id, activity_code='CM01',
                         source_type='comment', source_id=str(parent_c.comment_id))
        svc.award_points(student_id=student_id, activity_code='CM01',
                         source_type='comment', source_id=str(reply_c.comment_id))
        check(f"부모+대댓글 CM01 적립 후 누적 520 (실제: {svc.get_total_points(student_id)})",
              svc.get_total_points(student_id) == 520)

        # community.delete_comment()와 동일한 순서 재현 (수정된 로직)
        now = datetime.utcnow()
        parent_c.is_deleted = True
        parent_c.deleted_at = now
        svc.cancel_points('comment', parent_c.comment_id, '댓글 삭제')
        for reply in parent_c.replies:
            if reply.is_deleted:
                continue
            reply.is_deleted = True
            reply.deleted_at = now
            svc.cancel_points('comment', reply.comment_id, '부모 댓글 삭제')
        db.session.flush()

        check(f"부모 is_deleted=True (실제: {parent_c.is_deleted})", parent_c.is_deleted is True)
        check(f"대댓글도 is_deleted=True (실제: {reply_c.is_deleted})", reply_c.is_deleted is True)
        check(f"부모+대댓글 CM01 취소 후 누적 500으로 복귀 (실제: {svc.get_total_points(student_id)})",
              svc.get_total_points(student_id) == 500)

        # 중복 취소 방지 확인 - 같은 삭제 로직을 한 번 더 실행해도 0건이어야 함
        dup_cancel_parent = svc.cancel_points('comment', parent_c.comment_id, '댓글 삭제')
        dup_cancel_reply = svc.cancel_points('comment', reply_c.comment_id, '부모 댓글 삭제')
        check(f"부모 중복 취소 0건 (실제: {dup_cancel_parent}건)", dup_cancel_parent == 0)
        check(f"대댓글 중복 취소 0건 (실제: {dup_cancel_reply}건)", dup_cancel_reply == 0)
        check(f"중복 취소 시도 후에도 누적 500 그대로 (실제: {svc.get_total_points(student_id)})",
              svc.get_total_points(student_id) == 500)

        # 7. 대댓글 단독 삭제는 기존 동작 그대로(부모는 영향 없음)
        print("\n[7] 대댓글만 단독 삭제 -> 부모는 영향받지 않는가 (기존 동작 유지 확인)")
        parent_c2 = Comment(post_id=post3.post_id, user_id=student_user.user_id, content='부모 댓글2')
        db.session.add(parent_c2)
        db.session.flush()
        reply_c2 = Comment(post_id=post3.post_id, user_id=student_user.user_id, content='대댓글2',
                           parent_comment_id=parent_c2.comment_id)
        db.session.add(reply_c2)
        db.session.flush()
        parent2_id_val = parent_c2.comment_id
        reply2_id_val = reply_c2.comment_id

        svc.award_points(student_id=student_id, activity_code='CM01',
                         source_type='comment', source_id=str(parent_c2.comment_id))
        svc.award_points(student_id=student_id, activity_code='CM01',
                         source_type='comment', source_id=str(reply_c2.comment_id))

        # 대댓글(reply_c2)만 삭제 - comment.replies가 비어 있으니 루프가 아무 일도 안 함
        now2 = datetime.utcnow()
        reply_c2.is_deleted = True
        reply_c2.deleted_at = now2
        svc.cancel_points('comment', reply_c2.comment_id, '댓글 삭제')
        for reply in reply_c2.replies:
            if reply.is_deleted:
                continue
            reply.is_deleted = True
            reply.deleted_at = now2
            svc.cancel_points('comment', reply.comment_id, '부모 댓글 삭제')
        db.session.flush()

        check(f"대댓글만 is_deleted=True (실제: {reply_c2.is_deleted})", reply_c2.is_deleted is True)
        check(f"부모는 영향 없음 - is_deleted=False 그대로 (실제: {parent_c2.is_deleted})",
              parent_c2.is_deleted is False)
        check(f"대댓글 CM01만 취소, 부모 CM01은 유지 (누적 510, 실제: {svc.get_total_points(student_id)})",
              svc.get_total_points(student_id) == 510)

        # 8. 게시글 삭제 경로에서도 대댓글 포인트가 빠짐없이 회수되는가
        print("\n[8] 게시글 삭제 경로 -> 대댓글 포인트까지 전부 회수되는가")
        # community.delete()와 동일한 순서 재현: post_id 기준으로 parent_comment_id
        # 구분 없이 모든 살아있는 댓글(부모+대댓글)을 순회하며 취소한다.
        svc.cancel_points('post', post3.post_id, '게시글 삭제')  # 이 post엔 QS01 없음, 0건이 정상
        active_comments = Comment.query.filter_by(post_id=post3.post_id, is_deleted=False).all()
        active_ids = {c.comment_id for c in active_comments}
        check(f"post3에 아직 살아있는 댓글 1개(부모 댓글2) (실제: {active_ids == {parent_c2.comment_id}})",
              active_ids == {parent_c2.comment_id})
        for c in active_comments:
            svc.cancel_points('comment', c.comment_id, '게시글 삭제')
        db.session.flush()
        check(f"게시글 삭제 경로 처리 후 누적 500으로 복귀 (실제: {svc.get_total_points(student_id)})",
              svc.get_total_points(student_id) == 500)

    finally:
        # --- 테스트 데이터 정리 (어디서 실패했든 만들어진 것만 지운다) ---
        # finalize_essay()가 내부에서 commit()을 호출하므로 이 시점의 세션 상태가
        # 일부는 커밋됨/일부는 flush만 된 상태로 섞여 있을 수 있다. rollback 대신
        # 생성 시점에 미리 뽑아둔 문자열 ID로 전부 명시적으로 지우고 마지막에 commit한다.
        print("\n" + "=" * 70)
        print("테스트 데이터 정리 중...")

        PointEvent.query.filter_by(student_id=student_id).delete(synchronize_session=False)
        if comment_id_val is not None:
            Comment.query.filter_by(comment_id=comment_id_val).delete(synchronize_session=False)
        for cid in (reply_id_val, parent_id_val, reply2_id_val, parent2_id_val):
            if cid is not None:
                Comment.query.filter_by(comment_id=cid).delete(synchronize_session=False)
        if post_id_val is not None:
            Post.query.filter_by(post_id=post_id_val).delete(synchronize_session=False)
        if post2_id_val is not None:
            Post.query.filter_by(post_id=post2_id_val).delete(synchronize_session=False)
        if post3_id_val is not None:
            Post.query.filter_by(post_id=post3_id_val).delete(synchronize_session=False)
        if essay_id_val is not None:
            Essay.query.filter_by(essay_id=essay_id_val).delete(synchronize_session=False)
        Student.query.filter_by(student_id=student_id).delete(synchronize_session=False)
        User.query.filter(User.user_id.in_(
            [teacher.user_id, admin.user_id, student_user.user_id]
        )).delete(synchronize_session=False)
        db.session.commit()
        print("정리 완료 (테스트로 만든 User/Student/Essay/Post/Comment/PointEvent 전부 삭제됨)")

    print("\n" + "=" * 70)
    if failures:
        print(f"결과: {len(failures)}건 실패")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)
    else:
        print("결과: 전체 통과")
