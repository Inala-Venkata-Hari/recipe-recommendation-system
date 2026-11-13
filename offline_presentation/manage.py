"""Local-only presentation manager. No downloads, installs or remote services."""
import argparse,json,os,shutil,signal,socket,subprocess,sys,time,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parent
LOCAL_PYTHON=ROOT/'.venv'/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
LEGACY_PYTHON=ROOT.parent/'recipe-recommendation-system/.venv/bin/python'
PYTHON=Path(os.environ.get('PRESENTATION_PYTHON',str(LOCAL_PYTHON if LOCAL_PYTHON.exists() else LEGACY_PYTHON if LEGACY_PYTHON.exists() else Path(sys.executable))))
APPS={'original':('app.py',8601),'synthetic':('app.py',8602),'real-data':('usda_trial.py',8603)}
STATE=ROOT/'running.json'
def state():return json.loads(STATE.read_text()) if STATE.exists() else {}
def health(port):
    try:
        with urllib.request.urlopen(f'http://127.0.0.1:{port}/_stcore/health',timeout=2) as r:return r.status==200
    except Exception:return False
def stop():
    saved=state()
    for name,record in saved.items():
        # Only stop a process we started, checking its command against our isolated app path.
        try:
            pid=int(record['pid'])
            if os.name=='nt':
                cmd=subprocess.check_output(['powershell','-NoProfile','-Command',f'(Get-CimInstance Win32_Process -Filter \"ProcessId = {pid}\").CommandLine'],text=True).strip()
            elif Path(f'/proc/{pid}/cmdline').exists():
                cmd=Path(f'/proc/{pid}/cmdline').read_bytes().decode().replace('\0',' ')
            else:
                cmd=subprocess.check_output(['ps','-p',str(pid),'-o','command='],text=True).strip()
            if str(ROOT/'apps'/name) in cmd and 'streamlit' in cmd:
                subprocess.run(['taskkill','/PID',str(pid),'/T','/F'],check=False,stdout=subprocess.DEVNULL) if os.name=='nt' else os.kill(pid,signal.SIGTERM)
        except (FileNotFoundError,ProcessLookupError,subprocess.CalledProcessError):pass
    STATE.unlink(missing_ok=True)
def start():
    if not PYTHON.exists():raise SystemExit('Python environment missing. Set PRESENTATION_PYTHON to a Python with pandas and streamlit installed.')
    saved=state();(ROOT/'logs').mkdir(exist_ok=True)
    for name,(entry,port) in APPS.items():
        if name in saved and health(port):continue
        with socket.socket() as sock:
            try:sock.bind(('127.0.0.1',port))
            except OSError:raise SystemExit(f'Port {port} already used by another process. Stop that process or edit APPS ports.')
        folder=ROOT/'apps'/name;env=os.environ.copy()
        env.update(STREAMLIT_BROWSER_GATHER_USAGE_STATS='false',STREAMLIT_SERVER_HEADLESS='true')
        if name=='synthetic':env['RECIPE_DATA_DIR']=str(folder/'data/synthetic_demo')
        if name=='real-data':env.update(USDA_DATA_DIR=str(folder/'data/usda_trial'),USDA_WORK_DIR=str(folder/'data/usda_trial/workspace'))
        with (ROOT/'logs'/f'{name}.log').open('a') as log:
            process=subprocess.Popen([str(PYTHON),'-m','streamlit','run',str(folder/entry),'--server.address','127.0.0.1','--server.port',str(port),'--server.headless','true','--browser.gatherUsageStats','false'],cwd=folder,env=env,stdout=log,stderr=subprocess.STDOUT,**({'creationflags':subprocess.CREATE_NEW_PROCESS_GROUP} if os.name=='nt' else {'start_new_session':True}))
        saved[name]={'pid':process.pid,'port':port};STATE.write_text(json.dumps(saved,indent=2))
    for name,(_,port) in APPS.items():
        for _ in range(40):
            if health(port):break
            time.sleep(.25)
        if not health(port):raise SystemExit(f'{name} failed to start; inspect logs/{name}.log')
        print(f'{name}: http://localhost:{port}')
    print('Open index.html for the presentation menu. Internet is not required.')
def reset():
    stop();time.sleep(1)
    for source,target in [(ROOT/'seed/synthetic',ROOT/'apps/synthetic/data/synthetic_demo'),(ROOT/'seed/real-data',ROOT/'apps/real-data/data/usda_trial/workspace')]:
        shutil.rmtree(target);shutil.copytree(source,target)
    print('Only presentation copies restored to the prepared demo state.')
parser=argparse.ArgumentParser();parser.add_argument('action',choices=['start','stop','status','reset']);args=parser.parse_args()
if args.action=='start':start()
elif args.action=='stop':stop();print('Presentation servers stopped.')
elif args.action=='reset':reset()
else:
    for name,(_,port) in APPS.items():print(name,'READY' if health(port) else 'STOPPED',f'http://localhost:{port}')
