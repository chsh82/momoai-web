"""Run this isolated suite in a fresh process; do not mix its app shell into other suites."""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'reports/teacher-course-tabs'
FILES = ['app/teacher/routes.py', 'templates/teacher/courses.html']


def hashes():
    return {rel: hashlib.sha256((ROOT / rel).read_bytes()).hexdigest() for rel in FILES}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    before = hashes()
    env = dict(os.environ, PYTEST_DISABLE_PLUGIN_AUTOLOAD='1')
    command = [sys.executable, '-m', 'pytest', 'tests/teacher_course_tabs/test_courses.py', '-q', '-s', '--tb=short', '--junitxml=reports/teacher-course-tabs/final-junit.xml']
    result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True, encoding='utf-8', errors='replace')
    output = result.stdout + result.stderr
    (OUT / 'final-tests.txt').write_text(output, encoding='utf-8')
    after = hashes()
    receipt = {'python': sys.executable, 'command': command, 'exit_code': result.returncode, 'before': before, 'after': after, 'source_stable': before == after}
    if (OUT / 'final-junit.xml').exists():
        receipt['junit_suites'] = [suite.attrib for suite in ET.parse(OUT / 'final-junit.xml').getroot().iter('testsuite')]
    (OUT / 'verification.json').write_text(json.dumps(receipt, indent=2), encoding='utf-8')
    print(output)
    if before != after:
        print('REJECTED: candidate source drifted while tests ran')
        return 2
    return result.returncode


if __name__ == '__main__':
    raise SystemExit(main())
