import warnings
warnings.filterwarnings('ignore')
from app import create_app
from app.models import db
from sqlalchemy import inspect, text

app = create_app()
with app.app_context():
    inspector = inspect(db.engine)
    cols = [c['name'] for c in inspector.get_columns('inquiry_posts')]
    print('columns:', cols)
    if 'recipient_id' not in cols:
        db.session.execute(text('ALTER TABLE inquiry_posts ADD COLUMN recipient_id VARCHAR(36)'))
        db.session.commit()
        print('ADDED recipient_id')
    else:
        print('recipient_id already exists')
