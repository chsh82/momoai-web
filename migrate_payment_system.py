# -*- coding: utf-8 -*-
"""결제 시스템 마이그레이션
신규 테이블: payment_periods, holiday_weeks, session_adjustments
기존 수정: payments, course_enrollments, attendance
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), 'instance', 'momoai.db')

# ── 신규 테이블 ─────────────────────────────────────────────────────────────

CREATE_PAYMENT_PERIODS = """
CREATE TABLE IF NOT EXISTS payment_periods (
    period_id       VARCHAR(36) PRIMARY KEY,
    period_type     VARCHAR(20) NOT NULL,
    year            INTEGER NOT NULL,
    period_number   INTEGER NOT NULL,
    label           VARCHAR(50) NOT NULL,
    start_date      DATE NOT NULL,
    end_date        DATE NOT NULL,
    weeks_count     INTEGER NOT NULL DEFAULT 12,
    is_adjusted     BOOLEAN NOT NULL DEFAULT 0,
    adjusted_note   VARCHAR(200),
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);
"""

CREATE_HOLIDAY_WEEKS = """
CREATE TABLE IF NOT EXISTS holiday_weeks (
    holiday_id      VARCHAR(36) PRIMARY KEY,
    week_start      DATE NOT NULL,
    week_end        DATE NOT NULL,
    reason          VARCHAR(200) NOT NULL,
    created_by      VARCHAR(36) REFERENCES users(user_id) ON DELETE SET NULL,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);
"""

CREATE_SESSION_ADJUSTMENTS = """
CREATE TABLE IF NOT EXISTS session_adjustments (
    adjustment_id       VARCHAR(36) PRIMARY KEY,
    student_id          VARCHAR(36) NOT NULL REFERENCES students(student_id) ON DELETE CASCADE,
    enrollment_id       VARCHAR(36) NOT NULL REFERENCES course_enrollments(enrollment_id) ON DELETE CASCADE,
    attendance_id       VARCHAR(36) REFERENCES attendance(attendance_id) ON DELETE SET NULL,
    adjustment_type     VARCHAR(20),
    sessions_count      INTEGER NOT NULL DEFAULT 1,
    reason              TEXT,
    source              VARCHAR(20) NOT NULL,
    status              VARCHAR(20) NOT NULL DEFAULT 'pending_review',
    applied_payment_id  VARCHAR(36) REFERENCES payments(payment_id) ON DELETE SET NULL,
    reviewed_by         VARCHAR(36) REFERENCES users(user_id) ON DELETE SET NULL,
    reviewed_at         DATETIME,
    notified_teacher_at DATETIME,
    created_by          VARCHAR(36) REFERENCES users(user_id) ON DELETE SET NULL,
    created_at          DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at          DATETIME DEFAULT CURRENT_TIMESTAMP
);
"""

# ── 인덱스 ──────────────────────────────────────────────────────────────────

INDEX_SQLS = [
    "CREATE INDEX IF NOT EXISTS ix_payment_periods_type   ON payment_periods(period_type);",
    "CREATE INDEX IF NOT EXISTS ix_payment_periods_year   ON payment_periods(year);",
    "CREATE INDEX IF NOT EXISTS ix_holiday_weeks_start    ON holiday_weeks(week_start);",
    "CREATE INDEX IF NOT EXISTS ix_session_adj_student    ON session_adjustments(student_id);",
    "CREATE INDEX IF NOT EXISTS ix_session_adj_enrollment ON session_adjustments(enrollment_id);",
    "CREATE INDEX IF NOT EXISTS ix_session_adj_status     ON session_adjustments(status);",
    "CREATE INDEX IF NOT EXISTS ix_session_adj_type       ON session_adjustments(adjustment_type);",
]

# ── 기존 테이블 컬럼 추가 ────────────────────────────────────────────────────

PAYMENTS_ALTER = [
    "ALTER TABLE payments ADD COLUMN period_id VARCHAR(36) REFERENCES payment_periods(period_id) ON DELETE SET NULL;",
    "ALTER TABLE payments ADD COLUMN period_start DATE;",
    "ALTER TABLE payments ADD COLUMN period_end DATE;",
    "ALTER TABLE payments ADD COLUMN weekly_fee INTEGER;",
    "ALTER TABLE payments ADD COLUMN weeks_count INTEGER;",
    "ALTER TABLE payments ADD COLUMN is_prorated BOOLEAN DEFAULT 0;",
    "ALTER TABLE payments ADD COLUMN carried_over INTEGER DEFAULT 0;",
    "ALTER TABLE payments ADD COLUMN free_used INTEGER DEFAULT 0;",
    "ALTER TABLE payments ADD COLUMN manual_discount_note TEXT;",
    "ALTER TABLE payments ADD COLUMN sms_sent_at DATETIME;",
]

ENROLLMENTS_ALTER = [
    "ALTER TABLE course_enrollments ADD COLUMN payment_cycle VARCHAR(20);",
    "ALTER TABLE course_enrollments ADD COLUMN weekly_fee INTEGER;",
]

ATTENDANCE_ALTER = [
    "ALTER TABLE attendance ADD COLUMN adjustment_created BOOLEAN DEFAULT 0;",
]


def column_exists(cur, table, column):
    cur.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in cur.fetchall())


def run():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    print("1. 신규 테이블 생성...")
    cur.execute(CREATE_PAYMENT_PERIODS)
    print("   ✓ payment_periods")
    cur.execute(CREATE_HOLIDAY_WEEKS)
    print("   ✓ holiday_weeks")
    cur.execute(CREATE_SESSION_ADJUSTMENTS)
    print("   ✓ session_adjustments")

    print("2. 인덱스 생성...")
    for sql in INDEX_SQLS:
        cur.execute(sql)
    print("   ✓ 완료")

    print("3. payments 테이블 컬럼 추가...")
    for sql in PAYMENTS_ALTER:
        col = sql.split("ADD COLUMN ")[1].split()[0]
        if not column_exists(cur, 'payments', col):
            cur.execute(sql)
            print(f"   ✓ {col}")
        else:
            print(f"   - {col} (이미 존재)")

    print("4. course_enrollments 테이블 컬럼 추가...")
    for sql in ENROLLMENTS_ALTER:
        col = sql.split("ADD COLUMN ")[1].split()[0]
        if not column_exists(cur, 'course_enrollments', col):
            cur.execute(sql)
            print(f"   ✓ {col}")
        else:
            print(f"   - {col} (이미 존재)")

    print("5. attendance 테이블 컬럼 추가...")
    for sql in ATTENDANCE_ALTER:
        col = sql.split("ADD COLUMN ")[1].split()[0]
        if not column_exists(cur, 'attendance', col):
            cur.execute(sql)
            print(f"   ✓ {col}")
        else:
            print(f"   - {col} (이미 존재)")

    conn.commit()
    conn.close()
    print("\n✅ 결제 시스템 마이그레이션 완료!")


if __name__ == '__main__':
    run()
