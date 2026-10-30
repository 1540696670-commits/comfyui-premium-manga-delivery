import { app } from '/scripts/app.js';

const initialKind = new URLSearchParams(location.search).get('manga');
let requested = ['auto', 'rain-duel'].includes(initialKind);
let loading = false;
async function openComic(kind = 'auto') {
    if (loading) return;
    loading = true;
    requested = false;
    try {
        const file = kind === 'rain-duel' ? 'rain-duel.json' : 'auto-comic.json';
        const response = await fetch('/extensions/ComfyUI-Manga-Launcher/' + file);
        if (!response.ok) throw new Error('无法读取漫画工作流');
        await app.loadGraphData(await response.json());
        app.canvas.ds.scale = 0.65;
        app.canvas.ds.offset[0] = 580;
        app.canvas.ds.offset[1] = 180;
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
    setup() {
        const button = document.createElement('button');
        button.textContent = '高级漫画 · 自动分镜';
        button.id = 'manga-open-auto';
        button.title = '输入任意故事，自动策划镜头、分镜和漫画画面';
        button.style.cssText = 'position:fixed;top:54px;left:43%;z-index:1001;background:#7155ca;color:white;border:1px solid #a58de9;border-radius:8px;padding:8px 16px;font:14px sans-serif;cursor:pointer';
        button.addEventListener('click', () => openComic());
        document.body.appendChild(button);
    },
    afterConfigureGraph() {
        if (requested && !loading) queueMicrotask(() => openComic(initialKind));
    }
});

