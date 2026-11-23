"""Narrow approved exploration-only changes over the fixed upstream shell."""
from scripts.result_library_shell_overlay import overlay, GUARD

def overlay_upstream(raw):
    raw=raw.replace(b'\r\n',b'\n')
    marker=b"                            {% if current_user.role in ('admin', 'master_admin') or (current_user.role == 'student' and config.get('STUDENT_INTEREST_QUEST_ENABLED') == true) %}"
    if raw.count(marker)!=1:raise ValueError('Old exploration entry drift')
    start=raw.index(marker);end=raw.index(b'                            {% endif %}',start)+len(b'                            {% endif %}\n')
    if raw[start:end].count(b'<a ')!=1 or b'interest_quest.index' not in raw[start:end]:raise ValueError('Entry scope drift')
    raw=raw[:start]+raw[end:]
    anchor=b'                {% if current_user.has_permission_level(2) %}'
    if raw.count(anchor)!=1:raise ValueError('Common navigation anchor drift')
    member=('                {% if '+GUARD+' %}\n                <a href="{{ url_for(\'interest_quest.index\') }}"\n                   class="sidebar-link flex items-center gap-3 px-4 py-3 text-white text-opacity-80 hover:bg-white hover:bg-opacity-10 rounded-lg transition {% if request.endpoint and \'interest_quest.\' in request.endpoint %}bg-white bg-opacity-10{% endif %}">\n                    <span class="text-xl">🗺️</span><span class="font-medium">전공마을 탐험</span>\n                </a>\n                {% endif %}\n\n').encode()
    return overlay(raw.replace(anchor,member+anchor,1))
