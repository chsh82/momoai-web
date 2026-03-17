# -*- coding: utf-8 -*-
"""토스 페이먼츠 결제 라우트"""
import base64
import requests as http_requests
from datetime import datetime

from flask import render_template, redirect, url_for, request, jsonify, current_app, flash
from flask_login import login_required, current_user

from app.payment import payment_bp
from app.models import db
from app.models.payment import Payment


def _require_student_or_parent():
    if current_user.role not in ('student', 'parent', 'admin'):
        return False
    return True


def _can_pay(payment):
    """해당 결제 건에 접근 가능한지 확인"""
    if current_user.role == 'admin':
        return True
    if current_user.role == 'student':
        from app.models import Student
        student = Student.query.filter_by(user_id=current_user.user_id).first()
        return student and payment.student_id == student.student_id
    if current_user.role == 'parent':
        from app.models import ParentStudent
        linked = ParentStudent.query.filter_by(
            parent_id=current_user.user_id,
            student_id=payment.student_id,
            is_active=True
        ).first()
        return linked is not None
    return False


@payment_bp.route('/<payment_id>/checkout')
@login_required
def checkout(payment_id):
    """결제 체크아웃 페이지"""
    payment = Payment.query.get_or_404(payment_id)

    if not _can_pay(payment):
        flash('접근 권한이 없습니다.', 'error')
        return redirect(url_for('student.my_payments') if current_user.role == 'student'
                        else url_for('parent.all_payments'))

    if payment.status == 'completed':
        flash('이미 완료된 결제입니다.', 'info')
        return redirect(url_for('student.my_payments') if current_user.role == 'student'
                        else url_for('parent.all_payments'))

    if payment.status == 'cancelled':
        flash('취소된 청구서입니다.', 'error')
        return redirect(url_for('student.my_payments') if current_user.role == 'student'
                        else url_for('parent.all_payments'))

    client_key = current_app.config.get('TOSS_CLIENT_KEY', '')
    student = payment.student

    # 주문명 생성
    period_label = ''
    if payment.period_start:
        period_label = payment.period_start.strftime('%Y년 %m월')
    course_name = payment.course.course_name if payment.course else '수강료'
    order_name = f"{course_name} {period_label}".strip() or '수강료'

    return render_template('payment/checkout.html',
                           payment=payment,
                           student=student,
                           client_key=client_key,
                           order_name=order_name)


@payment_bp.route('/success')
@login_required
def success():
    """토스 결제 성공 콜백"""
    payment_key = request.args.get('paymentKey', '')
    order_id = request.args.get('orderId', '')
    amount = request.args.get('amount', '0')

    # 결제 건 조회
    payment = Payment.query.get(order_id)
    if not payment:
        flash('결제 정보를 찾을 수 없습니다.', 'error')
        return redirect(url_for('student.my_payments') if current_user.role == 'student'
                        else url_for('parent.all_payments'))

    # 금액 위변조 검증
    try:
        requested_amount = int(amount)
    except ValueError:
        flash('잘못된 결제 요청입니다.', 'error')
        return redirect(url_for('payment.checkout', payment_id=order_id))

    if requested_amount != int(payment.amount):
        current_app.logger.warning(
            f'[Toss] 금액 위변조 감지 payment_id={order_id} '
            f'DB={payment.amount} 요청={requested_amount}'
        )
        flash('결제 금액이 일치하지 않습니다.', 'error')
        return redirect(url_for('payment.checkout', payment_id=order_id))

    # 토스 승인 API 호출
    secret_key = current_app.config.get('TOSS_SECRET_KEY', '')
    auth_header = base64.b64encode(f'{secret_key}:'.encode()).decode()

    try:
        resp = http_requests.post(
            'https://api.tosspayments.com/v1/payments/confirm',
            headers={
                'Authorization': f'Basic {auth_header}',
                'Content-Type': 'application/json',
            },
            json={
                'paymentKey': payment_key,
                'orderId': order_id,
                'amount': requested_amount,
            },
            timeout=10
        )
        toss_data = resp.json()
    except Exception as e:
        current_app.logger.error(f'[Toss] 승인 API 오류: {e}')
        flash('결제 승인 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.', 'error')
        return redirect(url_for('payment.checkout', payment_id=order_id))

    if resp.status_code != 200:
        error_msg = toss_data.get('message', '결제 승인에 실패했습니다.')
        current_app.logger.warning(f'[Toss] 승인 실패: {toss_data}')
        return render_template('payment/result.html',
                               success=False,
                               error_message=error_msg,
                               payment=payment)

    # DB 업데이트
    payment.status = 'completed'
    payment.transaction_id = payment_key
    payment.payment_method = _map_toss_method(toss_data.get('method', ''))
    payment.paid_at = datetime.utcnow()
    db.session.commit()

    current_app.logger.info(f'[Toss] 결제 완료 payment_id={order_id} amount={requested_amount}')
    return render_template('payment/result.html',
                           success=True,
                           payment=payment,
                           toss_data=toss_data)


@payment_bp.route('/fail')
@login_required
def fail():
    """토스 결제 실패 콜백"""
    error_code = request.args.get('code', '')
    error_message = request.args.get('message', '결제가 취소되었습니다.')
    order_id = request.args.get('orderId', '')

    payment = Payment.query.get(order_id) if order_id else None
    return render_template('payment/result.html',
                           success=False,
                           error_message=error_message,
                           error_code=error_code,
                           payment=payment)


def _map_toss_method(method_str):
    """토스 결제 수단 문자열 → DB payment_method 값 매핑"""
    if '카드' in method_str:
        return 'card'
    if '계좌' in method_str or '이체' in method_str:
        return 'transfer'
    return 'card'
