"""Run isolated festival Chromium suite and preserve real stdout/JUnit."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[1]
if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--label',default='focused')
    parser.add_argument('-k',default='')
    args=parser.parse_args()
    # Use the invoking isolated/project interpreter; no uncommitted report config.
    out=ROOT/'reports/exploration-v4/momotown-v02-implementation/frontend'
    out.mkdir(parents=True,exist_ok=True)
    command=[sys.executable,'-m','pytest','tests/momotown_frontend','-q','--junitxml='+str(out/(args.label+'.xml'))]
    if args.k: command+=['-k',args.k]
    result=subprocess.run(command,cwd=ROOT,capture_output=True,text=True,encoding='utf8',errors='replace')
    (out/(args.label+'.log')).write_text(result.stdout+result.stderr,encoding='utf8')
    print(result.stdout,result.stderr)
    sys.exit(result.returncode)
