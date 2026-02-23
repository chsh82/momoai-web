"""진행 중인 첨삭을 강제로 취소하는 스크립트"""
import sys, os
sys.path.insert(0, '/home/chsh82/momoai_web')
os.chdir('/home/chsh82/momoai_web')
os.environ['DATABASE_URL'] = 'sqlite:///momoai.db'

from app import create_app
from app.models import db, Essay

app = create_app()

with app.app_context():
    processing = Essay.query.filter_by(status='processing').all()
    if not processing:
        print("진행 중인 첨삭 없음")
    else:
        for e in processing:
            print(f"취소: [{e.essay_id}] {e.title or '제목없음'} - {e.student.name if e.student else '?'}")
            e.status = 'failed'
        db.session.commit()
        print(f"총 {len(processing)}건 취소 완료")
