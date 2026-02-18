# -*- coding: utf-8 -*-
from app import create_app, db
from app.models.material import Material, MaterialDownload

app = create_app()

with app.app_context():
    print("Creating material tables...")
    db.create_all()
    print("Material tables created successfully!")
