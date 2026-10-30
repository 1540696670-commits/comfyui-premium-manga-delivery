"""Opt-in core upgrade for a NEW dedicated portable installation; preserves source backup."""
import argparse,pathlib,json,urllib.request,zipfile,shutil,datetime,subprocess,hashlib
KIT=pathlib.Path(__file__).resolve().parent
def main():
    p=argparse.ArgumentParser();p.add_argument('portable');a=p.parse_args()
    root=pathlib.Path(a.portable).resolve();py=root/'python_embeded/python.exe';core=root/'ComfyUI'
    if not py.is_file() or not (core/'main.py').is_file():raise SystemExit('Select a portable ROOT folder.')
    lock=json.loads((KIT/'core-lock.json').read_text())
    print('Use a separate clean portable installation, close its server before proceeding.')
    if input('Type INSTALL to install the pinned core and dependencies: ')!='INSTALL':raise SystemExit('Cancelled')
    archive=KIT/'vendor/ComfyUI-v0.43.0.zip'
    if not archive.is_file():
        archive=KIT/'ComfyUI-core-download.zip';urllib.request.urlretrieve(lock['archive_url'],archive)
    if hashlib.sha256(archive.read_bytes()).hexdigest()!=lock['archive_sha256']:raise RuntimeError('Core archive checksum mismatch')
    backup=root/'manga_install_backups'/('core_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
    preserved={'models','input','output','user','custom_nodes','.git'}
    with zipfile.ZipFile(archive) as z:
        prefix=z.namelist()[0].split('/')[0]+'/'
        for name in z.namelist():
            rel=pathlib.PurePosixPath(name[len(prefix):])
            if not rel.parts or name.endswith('/') or rel.parts[0] in preserved:continue
            if '..' in rel.parts or rel.is_absolute():raise RuntimeError('Invalid archive member')
            target=core.joinpath(*rel.parts)
            if target.exists():
                saved=backup.joinpath(*rel.parts);saved.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(target,saved)
            target.parent.mkdir(parents=True,exist_ok=True)
            with z.open(name) as src,target.open('wb') as dst:shutil.copyfileobj(src,dst)
    # Keep portable's torch build; no unrequested CUDA upgrade or global Python modification.
    req=KIT/'requirements-core.txt'
    subprocess.run([str(py),'-m','pip','install','-r',str(req)],check=True)
    subprocess.run([str(py),str(KIT/'install.py'),str(root),'--skip-pip'],check=True)
    print('Done. Backup:',backup)
    print('Run run_premium_manga.bat; if old-driver kernel error use --compat-sdpa.')
if __name__=='__main__':main()
