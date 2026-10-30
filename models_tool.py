"""Download, verify, split and merge exact model files. Standard library only."""
import argparse,hashlib,json,pathlib,urllib.request,shutil,time
KIT=pathlib.Path(__file__).resolve().parent
def digest(p):
    h=hashlib.sha256()
    with open(p,'rb') as f:
        while block:=f.read(8*1024*1024): h.update(block)
    return h.hexdigest()
def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=['download','verify','split','merge'])
    p.add_argument('models',help='ComfyUI/models folder');p.add_argument('--parts',default=str(KIT/'model_parts'))
    p.add_argument('--mirror',action='store_true');a=p.parse_args()
    root=pathlib.Path(a.models).resolve();parts=pathlib.Path(a.parts).resolve()
    records=json.loads((KIT/'models.json').read_text('utf-8'))
    if a.action in ('split','merge'): parts.mkdir(parents=True,exist_ok=True)
    for m in records:
        dest=root/m['path'];dest.parent.mkdir(parents=True,exist_ok=True)
        if a.action=='split':
            if not dest.is_file() or digest(dest)!=m['sha256']:raise RuntimeError('Source mismatch: '+str(dest))
            listing=[]
            with dest.open('rb') as f:
                n=1
                while True:
                    block=f.read(64*1024*1024)
                    if not block:break
                    part=parts/(dest.name+f'.part{n:03d}')
                    # Fixed 1.75 GiB per asset: below GitHub's 2 GiB cap.
                    left=1792*1024*1024
                    with part.open('wb') as out:
                        while block:
                            out.write(block);left-=len(block)
                            if left==0:break
                            block=f.read(min(64*1024*1024,left))
                    listing.append({'name':part.name,'size':part.stat().st_size,'sha256':digest(part)})
                    print('Split',part.name,flush=True);n+=1
            (parts/(dest.name+'.parts.json')).write_text(json.dumps(listing,indent=2))
            continue
        if dest.is_file() and dest.stat().st_size==m['size'] and digest(dest)==m['sha256']:
            print('OK',m['path'],flush=True);continue
        if a.action=='verify':raise RuntimeError('Missing or checksum mismatch: '+str(dest))
        tmp=dest.with_suffix(dest.suffix+'.partial')
        if a.action=='merge':
            listing=json.loads((parts/(dest.name+'.parts.json')).read_text())
            with tmp.open('wb') as out:
                for rec in listing:
                    src=parts/rec['name']
                    if src.stat().st_size!=rec['size'] or digest(src)!=rec['sha256']:raise RuntimeError('Bad part '+str(src))
                    with src.open('rb') as inp:shutil.copyfileobj(inp,out,8*1024*1024)
        else:
            url=m['mirror'] if a.mirror else m['url']
            offset=tmp.stat().st_size if tmp.exists() else 0
            req=urllib.request.Request(url,headers={'Range':f'bytes={offset}-','User-Agent':'Premium-Manga-Installer/1'})
            with urllib.request.urlopen(req,timeout=90) as resp:
                resume=offset and resp.status==206
                if resume and not resp.headers.get('Content-Range','').startswith(f'bytes {offset}-'):raise RuntimeError('Invalid resume response')
                with tmp.open('ab' if resume else 'wb') as out:
                    done=offset if resume else 0;last=time.monotonic()
                    while data:=resp.read(8*1024*1024):
                        out.write(data);done+=len(data)
                        if time.monotonic()-last>10:print(dest.name,f'{done/m["size"]:.1%}',flush=True);last=time.monotonic()
        if tmp.stat().st_size!=m['size'] or digest(tmp)!=m['sha256']:raise RuntimeError('Downloaded/merged file checksum mismatch; original preserved: '+str(tmp))
        if dest.exists():raise RuntimeError('Existing invalid file preserved. Rename it before replacing: '+str(dest))
        tmp.replace(dest);print('Verified',dest.name,flush=True)
if __name__=='__main__':main()
