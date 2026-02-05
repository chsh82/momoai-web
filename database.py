import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict
import json

DB_PATH = Path(__file__).parent / 'tasks.db'


def init_database():
    """데이터베이스 초기화 및 테이블 생성"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 단일 작업 테이블
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            task_id TEXT PRIMARY KEY,
            student_name TEXT,
            grade TEXT,
            status TEXT,
            html_path TEXT,
            pdf_path TEXT,
            created_at TIMESTAMP,
            completed_at TIMESTAMP
        )
    ''')

    # 일괄 작업 테이블
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS batch_tasks (
            batch_id TEXT PRIMARY KEY,
            total INTEGER,
            current INTEGER,
            current_student TEXT,
            status TEXT,
            created_at TIMESTAMP,
            completed_at TIMESTAMP
        )
    ''')

    # 일괄 작업 결과 테이블
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS batch_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_id TEXT,
            index_num INTEGER,
            student_name TEXT,
            grade TEXT,
            html_path TEXT,
            pdf_path TEXT,
            FOREIGN KEY (batch_id) REFERENCES batch_tasks(batch_id)
        )
    ''')

    conn.commit()
    conn.close()


def create_task(task_id: str, student_name: str, grade: str) -> None:
    """단일 작업 생성"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('''
        INSERT INTO tasks (task_id, student_name, grade, status, created_at)
        VALUES (?, ?, ?, 'processing', ?)
    ''', (task_id, student_name, grade, datetime.now()))

    conn.commit()
    conn.close()


def update_task(task_id: str, status: str, html_path: Optional[str] = None,
                pdf_path: Optional[str] = None) -> None:
    """단일 작업 업데이트"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    if status == 'completed':
        cursor.execute('''
            UPDATE tasks
            SET status = ?, html_path = ?, pdf_path = ?, completed_at = ?
            WHERE task_id = ?
        ''', (status, html_path, pdf_path, datetime.now(), task_id))
    else:
        cursor.execute('''
            UPDATE tasks
            SET status = ?, html_path = ?, pdf_path = ?
            WHERE task_id = ?
        ''', (status, html_path, pdf_path, task_id))

    conn.commit()
    conn.close()


def get_task(task_id: str) -> Optional[Dict]:
    """단일 작업 조회"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute('SELECT * FROM tasks WHERE task_id = ?', (task_id,))
    row = cursor.fetchone()

    conn.close()

    if row:
        return dict(row)
    return None


def create_batch_task(batch_id: str, total: int) -> None:
    """일괄 작업 생성"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('''
        INSERT INTO batch_tasks (batch_id, total, current, status, created_at)
        VALUES (?, ?, 0, 'processing', ?)
    ''', (batch_id, total, datetime.now()))

    conn.commit()
    conn.close()


def update_batch_status(batch_id: str, current: int, current_student: str) -> None:
    """일괄 작업 진행 상황 업데이트"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('''
        UPDATE batch_tasks
        SET current = ?, current_student = ?
        WHERE batch_id = ?
    ''', (current, current_student, batch_id))

    conn.commit()
    conn.close()


def complete_batch_task(batch_id: str) -> None:
    """일괄 작업 완료"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('''
        UPDATE batch_tasks
        SET status = 'completed', completed_at = ?
        WHERE batch_id = ?
    ''', (datetime.now(), batch_id))

    conn.commit()
    conn.close()


def fail_batch_task(batch_id: str) -> None:
    """일괄 작업 실패"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('''
        UPDATE batch_tasks
        SET status = 'failed', completed_at = ?
        WHERE batch_id = ?
    ''', (datetime.now(), batch_id))

    conn.commit()
    conn.close()


def get_batch_task(batch_id: str) -> Optional[Dict]:
    """일괄 작업 조회"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute('SELECT * FROM batch_tasks WHERE batch_id = ?', (batch_id,))
    row = cursor.fetchone()

    conn.close()

    if row:
        return dict(row)
    return None


def save_batch_result(batch_id: str, index: int, student_name: str, grade: str,
                      html_path: str, pdf_path: Optional[str] = None) -> None:
    """일괄 작업 결과 저장"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('''
        INSERT INTO batch_results
        (batch_id, index_num, student_name, grade, html_path, pdf_path)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (batch_id, index, student_name, grade, html_path, pdf_path))

    conn.commit()
    conn.close()


def get_batch_results(batch_id: str) -> List[Dict]:
    """일괄 작업 결과 목록 조회"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute('''
        SELECT * FROM batch_results
        WHERE batch_id = ?
        ORDER BY index_num
    ''', (batch_id,))

    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


def update_batch_result_pdf(batch_id: str, index: int, pdf_path: str) -> None:
    """일괄 작업 결과의 PDF 경로 업데이트"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('''
        UPDATE batch_results
        SET pdf_path = ?
        WHERE batch_id = ? AND index_num = ?
    ''', (pdf_path, batch_id, index))

    conn.commit()
    conn.close()


# 데이터베이스 초기화
init_database()
