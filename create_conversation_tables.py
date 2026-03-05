# -*- coding: utf-8 -*-
"""conversations, conversation_messages 테이블 생성 스크립트 (SQLite 직접 사용)
GCP 서버에서 1회 실행: python create_conversation_tables.py
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), 'instance', 'momoai.db')


def create_tables():
    if not os.path.exists(DB_PATH):
        print(f'[ERROR] DB not found: {DB_PATH}')
        return

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # conversations 테이블
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='conversations'")
    if cur.fetchone():
        print('[OK] conversations 테이블이 이미 존재합니다.')
    else:
        cur.execute('''
            CREATE TABLE conversations (
                conversation_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user1_id        VARCHAR(36) NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
                user2_id        VARCHAR(36) NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
                created_at      DATETIME    DEFAULT CURRENT_TIMESTAMP,
                last_message_at DATETIME    DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cur.execute('CREATE INDEX ix_conversations_user1_id ON conversations(user1_id)')
        cur.execute('CREATE INDEX ix_conversations_user2_id ON conversations(user2_id)')
        cur.execute('CREATE INDEX ix_conversations_last_message_at ON conversations(last_message_at)')
        conn.commit()
        print('[OK] conversations 테이블 생성 완료.')

    # conversation_messages 테이블
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='conversation_messages'")
    if cur.fetchone():
        print('[OK] conversation_messages 테이블이 이미 존재합니다.')
    else:
        cur.execute('''
            CREATE TABLE conversation_messages (
                message_id      INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id INTEGER NOT NULL REFERENCES conversations(conversation_id) ON DELETE CASCADE,
                sender_id       VARCHAR(36) NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
                body            TEXT        NOT NULL,
                is_read         INTEGER     DEFAULT 0,
                read_at         DATETIME    NULL,
                created_at      DATETIME    DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cur.execute('CREATE INDEX ix_conv_messages_conversation_id ON conversation_messages(conversation_id)')
        cur.execute('CREATE INDEX ix_conv_messages_sender_id ON conversation_messages(sender_id)')
        cur.execute('CREATE INDEX ix_conv_messages_is_read ON conversation_messages(is_read)')
        cur.execute('CREATE INDEX ix_conv_messages_created_at ON conversation_messages(created_at)')
        conn.commit()
        print('[OK] conversation_messages 테이블 생성 완료.')

    conn.close()


if __name__ == '__main__':
    create_tables()
