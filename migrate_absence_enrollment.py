#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""결석 예고 / 입반전반 예약 테이블 생성 마이그레이션"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from run import app
from app.models import db
from app.models.absence_notice import AbsenceNotice
from app.models.enrollment_schedule import EnrollmentSchedule

with app.app_context():
    db.create_all()
    print("✅ absence_notices, enrollment_schedules 테이블 생성 완료")
