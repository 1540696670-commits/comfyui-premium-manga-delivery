import { app } from '/scripts/app.js';

const initialKind = new URLSearchParams(location.search).get('manga');
const workflows = {
    auto: 'auto-comic.json',
    'rain-duel': 'rain-duel.json',
    photo: 'reference-photo.json',
    storyboard: 'reference-storyboard.json',
    check: 'reference-check.json',
    unified: 'unified-comic.json',
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
        const reference = ['photo', 'storyboard', 'check', 'unified'].includes(kind);
        app.canvas.ds.scale = kind === 'unified' ? 0.75 : reference ? 0.9 : 0.65;
        app.canvas.ds.offset[0] = kind === 'unified' ? 130 : reference ? 70 : 580;
        app.canvas.ds.offset[1] = kind === 'unified' ? 200 : reference ? 130 : 180;
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
        const response = await fetch('/object_info/MangaUnifiedComic');
        const unifiedAvailable = response.ok && Object.hasOwn(await response.json(), 'MangaUnifiedComic');
        const toolbar = document.createElement('div');
        toolbar.id = 'manga-workflow-switcher';
        toolbar.style.cssText = 'position:fixed;top:56px;left:250px;z-index:1001;display:flex;gap:6px;flex-wrap:wrap;max-width:calc(100vw - 650px)';
        for (const [kind, label, title] of [
            ['unified', '漫画工作台 · 上传可选，自动判断', '分镜先检查，参考图可选，无图自动分镜'],
        ]) {
            const button = document.createElement('button');
            button.textContent = label;
            button.id = 'manga-open-' + kind;
            button.title = title;
            button.style.cssText = 'background:#7155ca;color:white;border:1px solid #a58de9;border-radius:7px;padding:8px 12px;font:14px sans-serif;cursor:pointer';
            button.addEventListener('click', () => {
                if (!unifiedAvailable) {
                    const url = new URL(location.href);
                    url.port = '8195';
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

