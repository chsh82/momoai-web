"""
Test script to verify teaching materials and videos routes are properly registered.
"""
from app import create_app

app = create_app()

print("\n" + "="*80)
print("TEACHING MATERIALS & VIDEOS - ROUTE VERIFICATION")
print("="*80)

# Get all registered routes
routes = []
for rule in app.url_map.iter_rules():
    routes.append({
        'endpoint': rule.endpoint,
        'methods': ','.join(sorted(rule.methods - {'HEAD', 'OPTIONS'})),
        'path': str(rule)
    })

# Filter for our new routes
admin_material_routes = [r for r in routes if 'teaching_material' in r['endpoint'] or 'video' in r['endpoint'] and 'admin' in r['endpoint']]
student_material_routes = [r for r in routes if 'teaching_material' in r['endpoint'] or 'teaching_video' in r['endpoint'] and 'student' in r['endpoint']]
parent_material_routes = [r for r in routes if 'material' in r['endpoint'] or 'video' in r['endpoint'] and 'parent' in r['endpoint']]

print("\n[ADMIN PORTAL ROUTES]")
print("-" * 80)
for route in sorted(admin_material_routes, key=lambda x: x['path']):
    print(f"  {route['methods']:15} {route['path']:50} -> {route['endpoint']}")

print("\n[STUDENT PORTAL ROUTES]")
print("-" * 80)
for route in sorted(student_material_routes, key=lambda x: x['path']):
    print(f"  {route['methods']:15} {route['path']:50} -> {route['endpoint']}")

print("\n[PARENT PORTAL ROUTES]")
print("-" * 80)
for route in sorted(parent_material_routes, key=lambda x: x['path']):
    print(f"  {route['methods']:15} {route['path']:50} -> {route['endpoint']}")

# Check database tables
print("\n[DATABASE TABLES]")
print("-" * 80)
from app.models import db
from app.models.teaching_material import TeachingMaterial, TeachingMaterialDownload
from app.models.video import Video, VideoView

tables_to_check = [
    ('teaching_materials', TeachingMaterial),
    ('teaching_material_downloads', TeachingMaterialDownload),
    ('videos', Video),
    ('video_views', VideoView)
]

with app.app_context():
    for table_name, model in tables_to_check:
        try:
            count = model.query.count()
            print(f"  ✓ {table_name:40} - {count} records")
        except Exception as e:
            print(f"  ✗ {table_name:40} - ERROR: {str(e)}")

print("\n[MODELS IMPORTED]")
print("-" * 80)
models_list = [
    'TeachingMaterial',
    'TeachingMaterialDownload',
    'Video',
    'VideoView',
    'MakeupClassRequest'
]

from app import models
for model_name in models_list:
    if hasattr(models, model_name):
        print(f"  ✓ {model_name}")
    else:
        print(f"  ✗ {model_name} - NOT FOUND")

print("\n[UTILITY FUNCTIONS]")
print("-" * 80)
from app.utils.content_access import (
    can_access_content,
    extract_youtube_video_id,
    format_file_size,
    GRADE_MAP
)

utilities = [
    ('can_access_content', can_access_content),
    ('extract_youtube_video_id', extract_youtube_video_id),
    ('format_file_size', format_file_size),
    ('GRADE_MAP', GRADE_MAP)
]

for util_name, util_func in utilities:
    print(f"  ✓ {util_name}")

# Test YouTube ID extraction
print("\n[YOUTUBE ID EXTRACTION TEST]")
print("-" * 80)
test_urls = [
    'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
    'https://youtu.be/dQw4w9WgXcQ',
    'https://www.youtube.com/embed/dQw4w9WgXcQ'
]

for url in test_urls:
    video_id = extract_youtube_video_id(url)
    print(f"  {url:50} -> {video_id}")

# Test file size formatting
print("\n[FILE SIZE FORMATTING TEST]")
print("-" * 80)
test_sizes = [512, 2048, 1048576, 5242880, 1073741824]
for size in test_sizes:
    formatted = format_file_size(size)
    print(f"  {size:15} bytes -> {formatted}")

print("\n" + "="*80)
print("VERIFICATION COMPLETE")
print("="*80 + "\n")
