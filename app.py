from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for
from werkzeug.utils import secure_filename
from pathlib import Path
import uuid
import threading
import os

import config
import database
from momoai_core import MOMOAICore
from pdf_generator import PDFGenerator
from batch_processor import BatchProcessor, read_excel_file, read_csv_file

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = config.MAX_CONTENT_LENGTH
app.config['UPLOAD_FOLDER'] = config.UPLOAD_FOLDER

# Jinja2 custom filters
@app.template_filter('basename')
def basename_filter(path):
    """Extract basename from path"""
    return Path(path).name

# API 키 확인
if not config.ANTHROPIC_API_KEY:
    raise Exception("ANTHROPIC_API_KEY 환경변수가 설정되지 않았습니다.")


def allowed_file(filename):
    """파일 확장자 검증"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in config.ALLOWED_EXTENSIONS


# ==================== 페이지 라우트 ====================

@app.route('/')
def index():
    """메인 페이지"""
    return render_template('index.html')


@app.route('/result/<task_id>')
def result(task_id):
    """단일 첨삭 결과 페이지"""
    task = database.get_task(task_id)

    if not task:
        return "작업을 찾을 수 없습니다.", 404

    if task['status'] == 'processing':
        return render_template('processing.html', task_id=task_id)

    if task['status'] == 'failed':
        return "첨삭 중 오류가 발생했습니다.", 500

    # HTML 경로 확인
    if not task['html_path']:
        return "HTML 파일 경로가 없습니다. 첨삭이 제대로 완료되지 않았을 수 있습니다.", 500

    # HTML 파일 읽기
    try:
        with open(task['html_path'], 'r', encoding='utf-8') as f:
            html_content = f.read()
    except Exception as e:
        return f"HTML 파일을 읽을 수 없습니다: {e}", 500

    return render_template('result.html',
                         task_id=task_id,
                         student_name=task['student_name'],
                         grade=task['grade'],
                         html_content=html_content,
                         html_filename=Path(task['html_path']).name,
                         pdf_path=task['pdf_path'])


@app.route('/batch/progress/<batch_id>')
def batch_progress(batch_id):
    """일괄 첨삭 진행 상황 페이지"""
    batch_task = database.get_batch_task(batch_id)

    if not batch_task:
        return "일괄 작업을 찾을 수 없습니다.", 404

    return render_template('batch_progress.html',
                         batch_id=batch_id,
                         total=batch_task['total'])


@app.route('/batch/complete/<batch_id>')
def batch_complete(batch_id):
    """일괄 첨삭 완료 페이지"""
    batch_task = database.get_batch_task(batch_id)

    if not batch_task:
        return "일괄 작업을 찾을 수 없습니다.", 404

    if batch_task['status'] != 'completed':
        return redirect(url_for('batch_progress', batch_id=batch_id))

    # 결과 목록 조회
    results = database.get_batch_results(batch_id)

    return render_template('batch_complete.html',
                         batch_id=batch_id,
                         total=batch_task['total'],
                         results=results)


# ==================== API 라우트 ====================

@app.route('/api/review', methods=['POST'])
def api_review():
    """단일 첨삭 API"""
    try:
        data = request.json
        student_name = data.get('student_name', '').strip()
        grade = data.get('grade', '').strip()
        essay_text = data.get('essay_text', '').strip()

        # 입력 검증
        if not student_name or not grade or not essay_text:
            return jsonify({'error': '모든 필드를 입력해주세요.'}), 400

        # Task ID 생성
        task_id = str(uuid.uuid4())

        # DB에 작업 생성
        database.create_task(task_id, student_name, grade)

        # 백그라운드에서 첨삭 수행
        def process_review():
            try:
                momoai = MOMOAICore(config.ANTHROPIC_API_KEY)

                # 첨삭 수행
                html_content = momoai.analyze_essay(student_name, grade, essay_text)

                # HTML 저장
                filename = momoai.generate_filename(student_name, grade)
                html_path = momoai.save_html(html_content, filename)

                # 작업 완료
                database.update_task(task_id, 'completed', html_path=html_path)

            except Exception as e:
                import traceback
                print(f"=== ERROR in process_review ===")
                print(f"Task ID: {task_id}")
                print(f"Student: {student_name}")
                print(f"Error: {e}")
                print(f"Traceback:")
                traceback.print_exc()
                print(f"=== END ERROR ===")
                database.update_task(task_id, 'failed')

        thread = threading.Thread(target=process_review)
        thread.daemon = True
        thread.start()

        return jsonify({
            'task_id': task_id,
            'status': 'processing'
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/batch_review', methods=['POST'])
def api_batch_review():
    """일괄 첨삭 API"""
    try:
        # 파일 확인
        if 'file' not in request.files:
            return jsonify({'error': '파일이 업로드되지 않았습니다.'}), 400

        file = request.files['file']

        if file.filename == '':
            return jsonify({'error': '파일이 선택되지 않았습니다.'}), 400

        if not allowed_file(file.filename):
            return jsonify({'error': '지원하지 않는 파일 형식입니다. (.xlsx, .csv만 가능)'}), 400

        # 파일 저장
        filename = secure_filename(file.filename)
        file_path = config.UPLOAD_FOLDER / filename
        file.save(file_path)

        # 파일 읽기
        try:
            if filename.endswith('.xlsx'):
                df = read_excel_file(str(file_path))
            elif filename.endswith('.csv'):
                df = read_csv_file(str(file_path))
            else:
                return jsonify({'error': '지원하지 않는 파일 형식입니다.'}), 400
        except Exception as e:
            return jsonify({'error': str(e)}), 400

        # Batch ID 생성
        batch_id = str(uuid.uuid4())

        # DB에 일괄 작업 생성
        database.create_batch_task(batch_id, len(df))

        # 백그라운드에서 일괄 처리
        def process_batch():
            processor = BatchProcessor(batch_id, df, config.ANTHROPIC_API_KEY)
            processor.process_batch()

        thread = threading.Thread(target=process_batch)
        thread.daemon = True
        thread.start()

        return jsonify({
            'batch_id': batch_id,
            'total': len(df),
            'status': 'processing'
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/task_status/<task_id>')
def api_task_status(task_id):
    """단일 작업 상태 조회 API"""
    task = database.get_task(task_id)

    if not task:
        return jsonify({'error': '작업을 찾을 수 없습니다.'}), 404

    return jsonify({
        'task_id': task_id,
        'status': task['status'],
        'student_name': task['student_name'],
        'grade': task['grade']
    })


@app.route('/api/batch_status/<batch_id>')
def api_batch_status(batch_id):
    """일괄 작업 상태 조회 API"""
    batch_task = database.get_batch_task(batch_id)

    if not batch_task:
        return jsonify({'error': '일괄 작업을 찾을 수 없습니다.'}), 404

    # 완료된 결과 목록
    completed = database.get_batch_results(batch_id)

    progress = (batch_task['current'] / batch_task['total'] * 100) if batch_task['total'] > 0 else 0

    return jsonify({
        'batch_id': batch_id,
        'status': batch_task['status'],
        'total': batch_task['total'],
        'current': batch_task['current'],
        'current_student': batch_task['current_student'],
        'progress': round(progress, 1),
        'completed': [
            {
                'index': item['index_num'],
                'student_name': item['student_name'],
                'grade': item['grade'],
                'html_filename': Path(item['html_path']).name,
                'pdf_filename': Path(item['pdf_path']).name if item['pdf_path'] else None
            }
            for item in completed
        ]
    })


@app.route('/api/generate_pdf/<task_id>', methods=['POST'])
def api_generate_pdf(task_id):
    """PDF 생성 API (단일 작업)"""
    try:
        task = database.get_task(task_id)

        if not task:
            return jsonify({'error': '작업을 찾을 수 없습니다.'}), 404

        if not task['html_path']:
            return jsonify({'error': 'HTML 파일이 없습니다.'}), 400

        # PDF 생성
        pdf_generator = PDFGenerator()
        pdf_path = pdf_generator.generate_pdf(task['html_path'])

        # DB 업데이트
        database.update_task(task_id, task['status'], pdf_path=pdf_path)

        return jsonify({
            'pdf_path': pdf_path,
            'pdf_filename': Path(pdf_path).name,
            'status': 'success'
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/generate_batch_pdf/<batch_id>/<int:index>', methods=['POST'])
def api_generate_batch_pdf(batch_id, index):
    """PDF 생성 API (일괄 작업)"""
    try:
        results = database.get_batch_results(batch_id)
        result = next((r for r in results if r['index_num'] == index), None)

        if not result:
            return jsonify({'error': '결과를 찾을 수 없습니다.'}), 404

        if not result['html_path']:
            return jsonify({'error': 'HTML 파일이 없습니다.'}), 400

        # PDF 생성
        pdf_generator = PDFGenerator()
        pdf_path = pdf_generator.generate_pdf(result['html_path'])

        # DB 업데이트
        database.update_batch_result_pdf(batch_id, index, pdf_path)

        return jsonify({
            'pdf_path': pdf_path,
            'pdf_filename': Path(pdf_path).name,
            'status': 'success'
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/download/<path:filename>')
def api_download(filename):
    """파일 다운로드 API"""
    try:
        # HTML 또는 PDF 폴더에서 파일 찾기
        html_path = config.HTML_FOLDER / filename
        pdf_path = config.PDF_FOLDER / filename

        if html_path.exists():
            return send_file(html_path, as_attachment=True)
        elif pdf_path.exists():
            return send_file(pdf_path, as_attachment=True)
        else:
            return "파일을 찾을 수 없습니다.", 404

    except Exception as e:
        return str(e), 500


if __name__ == '__main__':
    import sys
    import io

    # Fix Windows console encoding
    if sys.platform == 'win32':
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

    print("=" * 50)
    print("MOMOAI v3.3.0 Web Version")
    print("=" * 50)
    print(f"HTML Output: {config.HTML_FOLDER}")
    print(f"PDF Output: {config.PDF_FOLDER}")
    print(f"Upload Folder: {config.UPLOAD_FOLDER}")
    print("=" * 50)
    print("Server starting...")
    print("URL: http://localhost:5000")
    print("=" * 50)

    app.run(debug=True, host='0.0.0.0', port=5000)
