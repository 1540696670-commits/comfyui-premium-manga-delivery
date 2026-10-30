import { app } from '/scripts/app.js';

const initialKind = new URLSearchParams(location.search).get('manga');
const workflows = {
    auto: 'auto-comic.json',
    'rain-duel': 'rain-duel.json',
    photo: 'reference-photo.json',
    storyboard: 'reference-storyboard.json',
    check: 'reference-check.json',
};
let requested = Object.hasOwn(workflows, initialKind);
let loading = false;
async function openComic(kind = 'auto') {
    if (loading) return;
    loading = true;
    requested = false;
    try {
        const file = workflows[kind] || workflows.auto;
        const response = await fetch('/extensions/ComfyUI-Manga-Launcher/' + file, { cache: 'no-store' });
        if (!response.ok) throw new Error('无法读取漫画工作流');
        await app.loadGraphData(await response.json());
        const reference = ['photo', 'storyboard', 'check'].includes(kind);
        app.canvas.ds.scale = reference ? 0.9 : 0.65;
        app.canvas.ds.offset[0] = reference ? 70 : 580;
        app.canvas.ds.offset[1] = reference ? 130 : 180;
        app.canvas.setDirty(true, true);
        const url = new URL(location.href);
        url.searchParams.delete('manga');
        history.replaceState(null, '', url);
    } catch (error) {
        alert('打开漫画失败：' + error.message);
    } finally {
        loading = false;
    }
}

app.registerExtension({
    name: 'Manga.OpenVerifiedWorkflow',
    async setup() {
        const response = await fetch('/object_info/MangaPanelExtract');
        const referenceAvailable = response.ok && Object.hasOwn(await response.json(), 'MangaPanelExtract');
        const toolbar = document.createElement('div');
        toolbar.id = 'manga-workflow-switcher';
        toolbar.style.cssText = 'position:fixed;top:56px;left:250px;z-index:1001;display:flex;gap:6px;flex-wrap:wrap;max-width:calc(100vw - 650px)';
        for (const [kind, label, title] of [
            ['auto', '自动分镜', '输入故事，自动规划漫画分镜'],
            ['photo', '上传参考照片', '保留原图人物和构图，转成漫画'],
            ['storyboard', '上传自带分镜', '逐格重绘，锁定已确认的分镜框线'],
            ['check', '先检查分镜框', '不加载模型，先核对分镜区域'],
        ]) {
            const button = document.createElement('button');
            button.textContent = label;
            button.id = 'manga-open-' + kind;
            button.title = title;
            button.style.cssText = 'background:#7155ca;color:white;border:1px solid #a58de9;border-radius:7px;padding:8px 12px;font:14px sans-serif;cursor:pointer';
            button.addEventListener('click', () => {
                if (kind !== 'auto' && !referenceAvailable) {
                    const url = new URL(location.href);
                    url.port = '8194';
                    url.search = '?manga=' + kind;
                    url.hash = '';
                    window.open(url.href, 'manga-reference', 'noopener');
                } else {
                    openComic(kind);
                }
            });
            toolbar.appendChild(button);
        }
        document.body.appendChild(toolbar);
    },
    afterConfigureGraph() {
        if (requested && !loading) queueMicrotask(() => openComic(initialKind));
    }
});

