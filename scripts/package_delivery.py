"""Rebuild the delivery ZIP and checksums without including Git or model weights."""
from pathlib import Path
import hashlib,zipfile
root=Path(__file__).resolve().parent.parent
excluded={'.git','__pycache__','model_parts','model-ci-temp'}
items=[]
for p in sorted(root.rglob('*')):
    rel=p.relative_to(root)
    if p.is_file() and not any(x in excluded for x in rel.parts) and p.name!='SHA256SUMS.txt' and not p.name.endswith(('.partial','.log','.safetensors')):
        items.append((p,rel.as_posix()))
(root/'SHA256SUMS.txt').write_text('\n'.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+rel for p,rel in items)+'\n',encoding='utf-8',newline='\n')
archive=root.parent/'PremiumManga-Delivery-v1.0.zip'
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
    for p,rel in items:z.write(p,'PremiumManga-Delivery/'+rel)
    z.write(root/'SHA256SUMS.txt','PremiumManga-Delivery/SHA256SUMS.txt')
with zipfile.ZipFile(archive) as z:assert z.testzip() is None
(archive.parent/(archive.name+'.sha256')).write_text(hashlib.sha256(archive.read_bytes()).hexdigest()+'  '+archive.name+'\n',encoding='ascii')
print('Verified ZIP',archive.stat().st_size,'bytes;',len(items)+1,'files')
