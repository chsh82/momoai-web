#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Course management system database migration script"""
from app import create_app
from app.models import db

def create_tables():
    """Create all new course management tables"""
    app = create_app('development')

    with app.app_context():
        # Create all tables
        db.create_all()
        print("✓ All database tables created successfully!")
        print("\nNew tables added:")
        print("  - courses")
        print("  - course_enrollments")
        print("  - course_sessions")
        print("  - attendance")
        print("  - payments")
        print("  - parent_student")
        print("  - teacher_feedback")
        print("  - announcements")
        print("  - announcement_reads")
        print("\nModified tables:")
        print("  - users (added role_level column)")
        print("  - students (added tier and tier_updated_at columns)")

if __name__ == '__main__':
    create_tables()
