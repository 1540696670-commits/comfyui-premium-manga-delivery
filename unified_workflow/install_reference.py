from pathlib import Path
import argparse,datetime,shutil,subprocess

HERE=Path(__file__).resolve().parent

def main():
    p=argparse.ArgumentParser();p.add_argument('portable');args=p.parse_args()
    root=Path(args.portable).resolve();core=root/'ComfyUI';py=root/'python_embeded/python.exe'
    if not py.is_file() or not (core/'main.py').is_file():raise SystemExit('请选择包含 ComfyUI 和 python_embeded 的便携版根目录。')
    # Existing unified installations load custom_nodes from ComfyUI_Manga too.
    node_root=(root/'ComfyUI_Manga/custom_nodes') if (root/'manga_setup/launch_unified.py').is_file() else core/'custom_nodes'
    backup=root/'manga_install_backups'/('reference_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
    for source in (HERE/'custom_nodes').iterdir():
        target=node_root/source.name
        if target.exists():
            shutil.copytree(target,backup/source.name)
        shutil.copytree(source,target,dirs_exist_ok=True)
    workflows=core/'user/default/workflows/MOSS漫画';workflows.mkdir(parents=True,exist_ok=True)
    for f in HERE.glob('0*.json'):shutil.copy2(f,workflows/f.name)
    if subprocess.run([str(py),'-c','import cv2'],capture_output=True).returncode:
        subprocess.run([str(py),'-m','pip','install','opencv-python-headless'],check=True)
    print('安装完成。请关闭并重新启动 ComfyUI，再打开 00 漫画工作台。')
    print('还需下载图片编辑 LoRA；原 v1.0 四模型继续复用，不用重复下载。')

if __name__=='__main__':main()
