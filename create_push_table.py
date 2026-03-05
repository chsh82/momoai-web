# -*- coding: utf-8 -*-
"""push_subscriptions 테이블 생성 스크립트 (SQLite 직접 사용)
GCP 서버에서 1회 실행: python create_push_table.py
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), 'instance', 'momoai.db')

def create_push_table():
    if not os.path.exists(DB_PATH):
        print(f'[ERROR] DB not found: {DB_PATH}')
        return

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # 테이블 존재 여부 확인
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='push_subscriptions'")
    exists = cur.fetchone()

    if exists:
        print('[OK] push_subscriptions 테이블이 이미 존재합니다.')
    else:
        cur.execute('''
            CREATE TABLE push_subscriptions (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id  VARCHAR(36) NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
                endpoint TEXT        NOT NULL UNIQUE,
                p256dh   TEXT        NOT NULL,
                auth     TEXT        NOT NULL,
                created_at DATETIME  DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cur.execute('CREATE INDEX ix_push_subscriptions_user_id ON push_subscriptions(user_id)')
        conn.commit()
        print('[OK] push_subscriptions 테이블 생성 완료.')

    conn.close()

if __name__ == '__main__':
    create_push_table()
