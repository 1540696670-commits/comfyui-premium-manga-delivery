"""Install only the bundled nodes/workflow into an existing portable installation."""
import argparse, datetime, hashlib, json, pathlib, shutil, subprocess, sys

KIT = pathlib.Path(__file__).resolve().parent

def main():
    p=argparse.ArgumentParser(description='Premium Manga portable installer')
    p.add_argument('portable', help='Folder containing python_embeded and ComfyUI')
    p.add_argument('--check-only',action='store_true')
    p.add_argument('--skip-pip',action='store_true')
    a=p.parse_args(); root=pathlib.Path(a.portable).expanduser().resolve()
    py=root/'python_embeded/python.exe'; core=root/'ComfyUI'
    if not py.is_file() or not (core/'main.py').is_file():
        raise SystemExit('Wrong folder. Select ComfyUI_windows_portable, not its ComfyUI subfolder.')
    print('Target:',root)
    missing=[]
    for m in json.loads((KIT/'models.json').read_text('utf-8')):
        f=core/'models'/m['path']
        if not f.is_file() or f.stat().st_size!=m['size']: missing.append(m['path'])
    print('Missing/incomplete weights:', len(missing))
    for x in missing: print('  ',x)
    if a.check_only: return
    # Backup only the node folders owned by this kit; never move user profiles/models.
    backup=root/'manga_install_backups'/datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    for src in (KIT/'custom_nodes').iterdir():
        dst=core/'custom_nodes'/src.name
        if dst.exists():
            backup.mkdir(parents=True,exist_ok=True)
            shutil.copytree(dst,backup/src.name)
        shutil.copytree(src,dst,dirs_exist_ok=True)
    wf=core/'user/default/workflows/MOSS漫画';wf.mkdir(parents=True,exist_ok=True)
    shutil.copy2(KIT/'workflow.json',wf/'高级自动漫画_参考图破框版.json')
    if not a.skip_pip:
        subprocess.run([str(py),'-m','pip','install','json-repair==0.64.2','opencv-python-headless'],check=True)
    # This additive launcher leaves the original GPU launcher untouched.
    shutil.copy2(KIT/'launch_manga.py',root/'launch_manga.py')
    (root/'run_premium_manga.bat').write_text('@echo off\ncd /d "%~dp0"\n"python_embeded\\python.exe" -s launch_manga.py %*\npause\n',encoding='ascii')
    print('Installed. Put models into ComfyUI/models and run run_premium_manga.bat.')
    print('Core must support MOSS Image and CLIP.generate; see the manual for tested versions.')

if __name__=='__main__': main()
