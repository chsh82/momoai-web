# Educational Content Management System - Implementation Complete

## Overview
Complete implementation of Teaching Materials (교재 관리) and Videos (동영상 관리) management system for MOMOAI v4.0.

**Implementation Date:** 2026-02-09
**Migration:** 7b9eefe90dff_add_teaching_materials_and_videos.py

## Features Implemented

### 1. Database Models

#### TeachingMaterial
- **Table:** `teaching_materials`
- **Fields:**
  - `material_id` (PK, UUID)
  - `title` (String 200)
  - `grade` (String 20, indexed) - 초1~고3
  - `original_filename` (String 255)
  - `storage_path` (String 500)
  - `file_size` (Integer)
  - `file_type` (String 50)
  - `publish_date` (Date, indexed)
  - `end_date` (Date, indexed)
  - `is_public` (Boolean, indexed)
  - `target_audience` (Text, JSON)
  - `download_count` (Integer)
  - `view_count` (Integer)
  - `created_at` (DateTime, indexed)
  - `created_by` (FK to User)
- **Supported File Types:** PDF, DOC, DOCX, PPT, PPTX, XLS, XLSX, HWP, ZIP

#### TeachingMaterialDownload
- **Table:** `teaching_material_downloads`
- **Fields:** download_id, material_id, user_id, student_id, downloaded_at
- **Purpose:** Track all material downloads for analytics

#### Video
- **Table:** `videos`
- **Fields:**
  - `video_id` (PK, UUID)
  - `title` (String 200)
  - `grade` (String 20, indexed)
  - `youtube_url` (String 500)
  - `youtube_video_id` (String 50) - Auto-extracted
  - `publish_date` (Date, indexed)
  - `end_date` (Date, indexed)
  - `is_public` (Boolean, indexed)
  - `target_audience` (Text, JSON)
  - `view_count` (Integer)
  - `created_at` (DateTime, indexed)
  - `created_by` (FK to User)

#### VideoView
- **Table:** `video_views`
- **Fields:** view_id, video_id, user_id, student_id, viewed_at
- **Purpose:** Track all video views for analytics

### 2. Target Audience System

Content can be targeted in two ways:

#### Grade-based Targeting
```json
{
  "type": "grade",
  "grades": ["초1", "초2", "중1", "고3"]
}
```
- Empty grades array = all grades
- Student's broad grade (초등/중등/고등) mapped to specific grades
- Grade mapping:
  - 초등 → 초1, 초2, 초3, 초4, 초5, 초6
  - 중등 → 중1, 중2, 중3
  - 고등 → 고1, 고2, 고3

#### Course-based Targeting
```json
{
  "type": "course",
  "course_ids": ["uuid-1", "uuid-2", "uuid-3"]
}
```
- Empty course_ids array = all courses
- Only students enrolled in specified courses can access
- Checks active enrollment status

### 3. Access Control

**Function:** `can_access_content(content, user, student)`

**Access Rules:**
1. Admin/Manager (role_level ≤ 2) → Full access
2. Content must be public (is_public = True)
3. Current date must be within publish_date and end_date
4. Student must match target audience (grade or course)

**Permission Hierarchy:**
- Level 1: Master Admin (full access)
- Level 2: Manager (full access)
- Level 3: Teacher (limited access)
- Level 4: Parent (child context only)
- Level 5: Student (own context only)

### 4. Admin Portal

#### Routes (requires permission_level ≤ 2)

**Teaching Materials:**
- `GET  /admin/teaching-materials` - List with filters
- `GET  /admin/teaching-materials/new` - Create form
- `POST /admin/teaching-materials/new` - Create action
- `GET  /admin/teaching-materials/<id>` - Detail view
- `GET  /admin/teaching-materials/<id>/edit` - Edit form
- `POST /admin/teaching-materials/<id>/edit` - Update action
- `POST /admin/teaching-materials/<id>/delete` - Delete action
- `GET  /admin/teaching-materials/<id>/download` - Download with logging

**Videos:**
- `GET  /admin/videos` - List with filters
- `GET  /admin/videos/new` - Create form
- `POST /admin/videos/new` - Create action
- `GET  /admin/videos/<id>` - Detail view
- `GET  /admin/videos/<id>/edit` - Edit form
- `POST /admin/videos/<id>/edit` - Update action
- `POST /admin/videos/<id>/delete` - Delete action

**API:**
- `GET  /admin/api/courses/search?q=keyword` - Course search for targeting

#### Features
- Statistics cards (total, active, by grade)
- Advanced filtering (grade, status, date range)
- File upload with validation
- Course search modal with AJAX
- Grade multi-select
- Download/view history
- Direct file download

#### Templates
- `templates/admin/teaching_materials.html` - List view
- `templates/admin/teaching_material_form.html` - Create/Edit form
- `templates/admin/teaching_material_detail.html` - Detail view
- `templates/admin/videos.html` - List view
- `templates/admin/video_form.html` - Create/Edit form
- `templates/admin/video_detail.html` - Detail with player

### 5. Student Portal

#### Routes (requires student role)
- `GET /student/teaching-materials` - List accessible materials
- `GET /student/teaching-materials/<id>` - Material detail
- `GET /student/teaching-materials/<id>/download` - Download with logging
- `GET /student/teaching-videos` - List accessible videos
- `GET /student/teaching-videos/<id>` - Video player with logging

#### Features
- Only shows content passing access control
- Search by title
- Filter by grade
- Statistics cards
- Download tracking
- View tracking
- Responsive card layout

#### Templates
- `templates/student/teaching_materials.html` - Material list
- `templates/student/teaching_material_detail.html` - Material detail
- `templates/student/teaching_videos.html` - Video list
- `templates/student/teaching_video_player.html` - Video player

### 6. Parent Portal

#### Routes (requires parent role)
- `GET /parent/materials` - Child selection for materials
- `GET /parent/materials/<student_id>` - Materials for child
- `GET /parent/materials/<student_id>/<material_id>` - Material detail
- `GET /parent/materials/<student_id>/<material_id>/download` - Download
- `GET /parent/videos` - Child selection for videos
- `GET /parent/videos/<student_id>` - Videos for child
- `GET /parent/videos/<student_id>/<video_id>` - Video player

#### Features
- Must have valid ParentStudent relationship
- View all content accessible to child
- Same filtering as student portal
- Download on behalf of child
- View tracking with parent context

#### Templates
- `templates/parent/materials_index.html` - Child selection
- `templates/parent/child_materials.html` - Material list for child
- `templates/parent/child_material_detail.html` - Material detail
- `templates/parent/videos_index.html` - Child selection
- `templates/parent/child_videos.html` - Video list for child
- `templates/parent/child_video_player.html` - Video player

### 7. Utility Functions

**File:** `app/utils/content_access.py`

#### Functions
- `can_access_content(content, user, student)` - Main access control
- `extract_youtube_video_id(url)` - Extract video ID from YouTube URLs
- `format_file_size(bytes)` - Human-readable file sizes (B, KB, MB, GB)
- `GRADE_MAP` - Dictionary mapping broad grades to specific grades

#### YouTube URL Support
- `https://www.youtube.com/watch?v=VIDEO_ID`
- `https://youtu.be/VIDEO_ID`
- `https://www.youtube.com/embed/VIDEO_ID`

### 8. Menu Items

**Admin Sidebar** (after "전체 수업현황"):
- 📚 교재 관리 → /admin/teaching-materials
- 🎬 동영상 관리 → /admin/videos

**Student Sidebar** (after "보강수업 신청"):
- 📚 학습 교재 → /student/teaching-materials
- 🎬 학습 동영상 → /student/teaching-videos

**Parent Sidebar** (after "과제 및 첨삭"):
- 📚 학습 교재 → /parent/materials
- 🎬 학습 동영상 → /parent/videos

## File Structure

```
momoai_web/
├── app/
│   ├── models/
│   │   ├── teaching_material.py (NEW)
│   │   └── video.py (NEW)
│   ├── utils/
│   │   └── content_access.py (NEW)
│   ├── admin/
│   │   ├── forms.py (UPDATED - added TeachingMaterialForm, VideoForm)
│   │   └── routes.py (UPDATED - added 16 new routes)
│   ├── student_portal/
│   │   └── routes.py (UPDATED - added 5 new routes)
│   └── parent_portal/
│       └── routes.py (UPDATED - added 7 new routes)
├── templates/
│   ├── admin/
│   │   ├── teaching_materials.html (NEW)
│   │   ├── teaching_material_form.html (NEW)
│   │   ├── teaching_material_detail.html (NEW)
│   │   ├── videos.html (NEW)
│   │   ├── video_form.html (NEW)
│   │   └── video_detail.html (NEW)
│   ├── student/
│   │   ├── teaching_materials.html (NEW)
│   │   ├── teaching_material_detail.html (NEW)
│   │   ├── teaching_videos.html (NEW)
│   │   └── teaching_video_player.html (NEW)
│   └── parent/
│       ├── materials_index.html (NEW)
│       ├── child_materials.html (NEW)
│       ├── child_material_detail.html (NEW)
│       ├── videos_index.html (NEW)
│       ├── child_videos.html (NEW)
│       └── child_video_player.html (NEW)
└── migrations/
    └── versions/
        └── 7b9eefe90dff_add_teaching_materials_and_videos.py (NEW)
```

## Usage Examples

### Admin: Create Material with Grade-based Targeting

1. Navigate to: `/admin/teaching-materials/new`
2. Fill in:
   - Title: "초등 1학년 영어 교재"
   - Grade: 초1
   - Upload file: textbook.pdf
   - Publish Date: 2026-02-01
   - End Date: 2026-12-31
   - Target Type: 학년별
   - Target Grades: [초1, 초2]
3. Submit → Material created and accessible to 초등 students

### Admin: Create Video with Course-based Targeting

1. Navigate to: `/admin/videos/new`
2. Fill in:
   - Title: "정규반 문법 강의"
   - Grade: 중1
   - YouTube URL: https://www.youtube.com/watch?v=abc123
   - Target Type: 수업별
   - Search and select courses
3. Submit → Video only visible to enrolled students

### Student: Access Materials

1. Navigate to: `/student/teaching-materials`
2. See only materials matching:
   - Student's grade (초등 → 초1-6 materials)
   - Student's enrolled courses
   - Current date within publish range
3. Click material → Download tracked

### Parent: View Child's Materials

1. Navigate to: `/parent/materials`
2. Select child
3. See same materials child can access
4. Download on behalf of child

## Testing Checklist

- [x] Database migration successful
- [x] Models import correctly
- [x] Routes registered properly
- [x] Access control function works
- [x] YouTube ID extraction works
- [x] File size formatting works
- [ ] Upload material as admin
- [ ] Create video as admin
- [ ] Access material as student
- [ ] Access video as student
- [ ] Parent can view child's materials
- [ ] Download tracking works
- [ ] View tracking works
- [ ] Grade-based targeting works
- [ ] Course-based targeting works
- [ ] Date-based visibility works

## Security Considerations

1. **File Upload Validation:**
   - Only allowed extensions
   - Secure filename handling
   - UUID-based storage naming

2. **Access Control:**
   - All routes protected by decorators
   - Access checks on every request
   - Parent-child relationship verified

3. **SQL Injection:**
   - All queries use SQLAlchemy ORM
   - No raw SQL queries

4. **XSS Prevention:**
   - All user input escaped in templates
   - Flask auto-escaping enabled

## Performance Optimization

1. **Database Indexes:**
   - grade, publish_date, end_date, is_public, created_at
   - Faster filtering and sorting

2. **Eager Loading:**
   - Consider adding join loads for creator relationships
   - Reduce N+1 query problems

3. **Caching:**
   - Consider caching active materials list
   - Redis integration for future

## Future Enhancements

1. **Material Versioning:** Track material updates
2. **Video Playlists:** Group related videos
3. **Material Ratings:** Student feedback on materials
4. **Completion Tracking:** Track video watch progress
5. **Automatic Notifications:** Notify when new content added
6. **Bulk Upload:** Upload multiple materials at once
7. **Material Categories:** Organize by subject/topic
8. **Download Limits:** Restrict number of downloads per student

## Maintenance

### Adding New File Types
Edit `TeachingMaterialForm` in `app/admin/forms.py`:
```python
FileAllowed(['pdf', 'doc', ..., 'NEW_TYPE'])
```

### Adjusting Access Rules
Edit `can_access_content()` in `app/utils/content_access.py`

### Migration Rollback
```bash
python -m flask db downgrade
```

## Support

For issues or questions:
1. Check this documentation
2. Review error logs in console
3. Check database integrity
4. Verify file permissions on uploads/ directory

---

**Implementation Status:** ✅ COMPLETE
**Last Updated:** 2026-02-09
