"""Build a review-only narrow sidebar overlay; never connects to a server."""
from pathlib import Path
import difflib,hashlib,json
ROOT=Path(__file__).resolve().parents[1]
GUARD="current_user.is_authenticated and current_user.is_active and current_user.role in ('student', 'parent', 'teacher', 'staff', 'manager', 'admin', 'master_admin') and (config.get('MEMBER_INTEREST_QUEST_ENABLED') == true or current_user.role in ('admin', 'master_admin') or (current_user.role == 'student' and config.get('STUDENT_INTEREST_QUEST_ENABLED') == true))"
ANCHOR='                    <span class="text-xl">🗺️</span><span class="font-medium">전공마을 탐험</span>\n                </a>'
PARENT='''
                {% if current_user.role == 'parent' %}
                <a data-interest-layer href="{{ url_for('interest_quest.children_page') }}"
                   class="sidebar-link flex items-center gap-3 px-4 py-3 text-white text-opacity-80 hover:bg-white hover:bg-opacity-10 rounded-lg transition">
                    <span class="text-xl">📁</span><span class="font-medium">자녀 탐색 결과</span>
                </a>
                {% endif %}'''
INCLUDE="    {% if "+GUARD+" %}\n    {% include 'interest_quest/layer.html' %}\n    {% endif %}\n"

def overlay(raw):
    newline=b'\r\n' if b'\r\n' in raw else b'\n'
    anchor=ANCHOR.encode().replace(b'\n',newline)
    if raw.count(anchor)!=1 or raw.count(b'</body>')!=1:raise ValueError('Shared shell baseline drift; review exact anchor before applying')
    return raw.replace(anchor,anchor+PARENT.encode().replace(b'\n',newline),1).replace(b'</body>',INCLUDE.encode().replace(b'\n',newline)+b'</body>',1)

if __name__=='__main__':
    source=Path('C:/Users/aproa/momoai_web/reports/reading-quiz-title-followup-20261120/deployed/templates/base.html')
    out=ROOT/'reports/result-library-20261121/integration';out.mkdir(parents=True,exist_ok=True)
    raw=source.read_bytes();candidate=overlay(raw)
    (out/'base-live-snapshot.html').write_bytes(raw)
    (out/'base-live-candidate.html').write_bytes(candidate)
    (out/'base-live-overlay.patch').write_text(''.join(difflib.unified_diff(raw.decode().splitlines(True),candidate.decode().splitlines(True),fromfile='a/templates/base.html',tofile='b/templates/base.html')),encoding='utf8')
    (out/'baseline.json').write_text(json.dumps(dict(source=str(source),source_sha256=hashlib.sha256(raw).hexdigest(),candidate_sha256=hashlib.sha256(candidate).hexdigest(),scope='review-only; snapshot compatibility, not current live verification'),indent=2),encoding='utf8')
    print('Review-only shared shell overlay',out)
