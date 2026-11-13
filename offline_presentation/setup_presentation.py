"""Run once with internet access on the destination laptop. No data download needed."""
import os,subprocess,sys,venv
from pathlib import Path
ROOT=Path(__file__).resolve().parent
if sys.version_info<(3,11):raise SystemExit('Use Python 3.11 or newer.')
target=ROOT/'.venv'
if not target.exists():venv.EnvBuilder(with_pip=True).create(target)
python=target/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
subprocess.run([str(python),'-m','pip','install','-r',str(ROOT/'requirements.txt')],check=True)
print('Setup complete. Run: python manage.py start (or START_DEMOS.sh on Linux/macOS).')
print('The apps and data are already included. Internet is not required after setup.')
