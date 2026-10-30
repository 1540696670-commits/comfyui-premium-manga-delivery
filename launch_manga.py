"""Portable, additive 8GB launch profile; no on-disk core patch."""
import os,pathlib,runpy,sys
root=pathlib.Path(__file__).resolve().parent
core=root/'ComfyUI';os.chdir(core);sys.path.insert(0,str(core))
# --compat-sdpa is removed before ComfyUI parses command-line arguments.
compat='--compat-sdpa' in sys.argv
if compat:sys.argv.remove('--compat-sdpa')
sys.argv=[str(core/'main.py'),'--windows-standalone-build','--disable-pinned-memory',
          '--lowvram','--reserve-vram','1','--use-pytorch-cross-attention',*sys.argv[1:]]
for stream in (sys.stdout,sys.stderr):
    if hasattr(stream,'reconfigure'):stream.reconfigure(encoding='utf-8',errors='replace')
if compat:
    # Explicit opt-in equivalent of the validated old-driver attention workaround.
    import comfy.ldm.modules.attention as attention
    attention.COMFY_KITCHEN_INT8_ATTENTION_IS_AVAILABLE=False
runpy.run_path(str(core/'main.py'),run_name='__main__')
