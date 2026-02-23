"""Create teaching_material_files table and update alembic version."""
import sys
sys.stdout.reconfigure(encoding='utf-8')

from app import create_app
app = create_app('development')

with app.app_context():
    from app.models import db
    from app.models.teaching_material import TeachingMaterialFile
    from sqlalchemy import inspect, text

    tables = inspect(db.engine).get_table_names()
    if 'teaching_material_files' not in tables:
        db.create_all()
        print('teaching_material_files table created')
    else:
        print('teaching_material_files table already exists')

    # Update alembic version
    db.session.execute(text("UPDATE alembic_version SET version_num='8e602ed5ed61'"))
    db.session.commit()
    print('Alembic version updated to 8e602ed5ed61')
    print('Done.')
