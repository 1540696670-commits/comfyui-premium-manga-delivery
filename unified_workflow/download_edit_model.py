from pathlib import Path
import argparse,json,hashlib,urllib.request
HERE=Path(__file__).resolve().parent

def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        while block:=f.read(8*1024*1024):h.update(block)
    return h.hexdigest()

def main():
    p=argparse.ArgumentParser();p.add_argument('portable');p.add_argument('--source',help='Optional downloaded LoRA file');a=p.parse_args()
    root=Path(a.portable).resolve()
    if not (root/'ComfyUI/main.py').is_file():raise SystemExit('请选择正确的便携版根目录。')
    m=json.loads((HERE/'edit_model.json').read_text('utf-8'));dest=root/'ComfyUI/models/loras'/m['filename'];dest.parent.mkdir(parents=True,exist_ok=True)
    if dest.is_file() and sha(dest)==m['sha256']:print('已校验，无需重复下载。');return
    if dest.exists():raise SystemExit('已有同名文件未通过校验，请先改名留存后重试。')
    tmp=dest.with_suffix('.partial')
    if a.source:
        import shutil
        source=Path(a.source).resolve()
        if sha(source)!=m['sha256']:raise SystemExit('提供的 LoRA 文件未通过校验。')
        shutil.copyfile(source,tmp)
    else:urllib.request.urlretrieve(m['url'],tmp)
    if tmp.stat().st_size!=m['size'] or sha(tmp)!=m['sha256']:raise SystemExit('下载文件校验失败，未安装。请重试。')
    tmp.replace(dest);print('图片编辑 LoRA 下载并校验完成。')

if __name__=='__main__':main()
