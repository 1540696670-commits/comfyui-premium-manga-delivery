"""Fetch original public weights on the runner, verify, then upload exact release parts."""
import hashlib,json,pathlib,subprocess,sys,urllib.request,time,shutil
ROOT=pathlib.Path(__file__).resolve().parent.parent
model=json.loads((ROOT/'models.json').read_text())[int(sys.argv[1])]
records=json.loads((ROOT/'release-assets.json').read_text())
parts=[r for r in records if r['name'].startswith(pathlib.Path(model['path']).name+'.part')]
repo=sys.argv[2]
def api(path):return json.loads(subprocess.check_output(['gh','api',path],text=True))
release=next(r for r in api('repos/'+repo+'/releases') if r['tag_name']=='v1.0')
assets={a['name']:a for a in release['assets']}
if all(r['name'] in assets and assets[r['name']].get('digest')=='sha256:'+r['sha256'] and assets[r['name']]['state']=='uploaded' for r in parts):
    print('All parts already verified');sys.exit(0)
tmp=pathlib.Path('model-ci-temp');tmp.mkdir(exist_ok=True);full=tmp/'weight.safetensors'
if shutil.disk_usage(tmp).free < model['size']+max(r['size'] for r in parts)+512*1024**2:raise RuntimeError('Insufficient runner disk space')
for attempt in range(4):
    try:
        h=hashlib.sha256();total=0;last=time.monotonic()
        with urllib.request.urlopen(model['url'],timeout=120) as resp,full.open('wb') as dst:
            while block:=resp.read(16*1024*1024):
                dst.write(block);h.update(block);total+=len(block)
                if time.monotonic()-last>15:print('Downloaded',round(total/model['size']*100,1),'%',flush=True);last=time.monotonic()
        assert total==model['size'] and h.hexdigest()==model['sha256'],'Original weight verification failed'
        break
    except Exception:
        if attempt==3:raise
        time.sleep(5)
print('Verified original weight SHA256',flush=True)
with full.open('rb') as src:
    for rec in parts:
        p=tmp/rec['name'];h=hashlib.sha256();left=rec['size']
        with p.open('wb') as out:
            while left:
                block=src.read(min(left,16*1024*1024))
                if not block:raise RuntimeError('Unexpected EOF')
                out.write(block);h.update(block);left-=len(block)
        assert h.hexdigest()==rec['sha256']
        a=assets.get(p.name)
        if not a or a.get('digest')!='sha256:'+rec['sha256'] or a['state']!='uploaded':
            for attempt in range(4):
                r=subprocess.run(['gh','release','upload','v1.0',str(p),'--repo',repo,'--clobber'])
                if r.returncode==0:break
                if attempt==3:raise RuntimeError('Upload failed '+p.name)
                time.sleep(5)
        print('Uploaded/verified',p.name,flush=True);p.unlink()
full.unlink()
manifest=tmp/(pathlib.Path(model['path']).name+'.parts.json');manifest.write_text(json.dumps(parts,indent=2))
subprocess.run(['gh','release','upload','v1.0',str(manifest),'--repo',repo,'--clobber'],check=True)
