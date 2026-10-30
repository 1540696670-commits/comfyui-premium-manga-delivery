import { app } from '/scripts/app.js';
import { api } from '/scripts/api.js';

app.registerExtension({
    name: 'Manga.UnifiedComicInputs',
    nodeCreated(node) {
        if (node.comfyClass !== 'MangaUnifiedComic') return;
        const widget = (name) => node.widgets.find(w => w.name === name);
        const set = (name, value) => { widget(name).value = value; };
        for (const name of ['storyboard', 'reference', 'stage', 'confirmed_layout']) {
            const w = widget(name);
            w.type = 'hidden';
            w.computeSize = () => [0, -4];
        }
        const root = document.createElement('div');
        root.style.cssText = 'box-sizing:border-box;padding:12px;background:#25212f;color:#eee;font:14px/1.55 sans-serif;border-radius:10px;overflow:auto;height:100%;';
        const hint = document.createElement('div');
        hint.textContent = '两张图均可不传。有分镜先检查；只有参考图就转绘；都不传则自动分镜。同时上传：分镜定布局，参考图辅助外观。';
        hint.style.cssText = 'color:#d1c0f5;margin-bottom:10px';
        root.appendChild(hint);
        const uploads = document.createElement('div');
        uploads.style.cssText = 'display:grid;grid-template-columns:1fr 1fr;gap:8px';
        root.appendChild(uploads);
        const status = document.createElement('div');
        status.style.cssText = 'padding:8px;margin:8px 0;background:#17151e;white-space:pre-wrap;border-radius:6px';
        const panels = {};
        function refresh() {
            for (const [key, panel] of Object.entries(panels)) {
                const name = widget(key).value;
                panel.label.textContent = name || '未上传（可选）';
                panel.clear.disabled = !name;
                panel.preview.style.display = name ? 'block' : 'none';
                if (name) panel.preview.src = api.apiURL('/view?' + new URLSearchParams({ filename: name, type: 'input' }));
            }
            confirm.disabled = !widget('storyboard').value || !widget('confirmed_layout').value;
            check.disabled = !widget('storyboard').value;
        }
        function resetCheck() {
            set('confirmed_layout', '');
            set('stage', '自动判断（分镜先检查）');
        }
        async function queue(confirmed = false) {
            set('stage', confirmed ? '确认格框并生成' : '自动判断（分镜先检查）');
            for (const n of app.graph._nodes) {
                if (n.type === 'SaveImage') {
                    const prefix = n.widgets?.find(w => w.name === 'filename_prefix');
                    if (prefix) prefix.value = widget('storyboard').value && !confirmed ? 'MangaUnified/PanelCheck' : 'MangaUnified/Comic';
                }
            }
            status.textContent = widget('storyboard').value && !confirmed ? '正在检查分镜框，本次不加载绘图模型…' : '已排队，将按上传内容自动选择生成方式。';
            try { await app.queuePrompt(0, 1); }
            catch (e) { status.textContent = '排队失败：' + e.message; }
        }
        function button(text, action) {
            const b = document.createElement('button');
            b.textContent = text;
            b.style.cssText = 'padding:7px 10px;margin:4px 5px 4px 0;border:1px solid #967dc9;border-radius:6px;background:#7053ba;color:white;cursor:pointer;font:14px sans-serif';
            b.addEventListener('click', action);
            return b;
        }
        for (const [key, title] of [['storyboard', '上传分镜图（可选）'], ['reference', '上传参考图（可选）']]) {
            const box = document.createElement('div');
            box.style.cssText = 'padding:8px;border:1px solid #62516f;border-radius:7px;margin:8px 0';
            const input = document.createElement('input');
            input.type = 'file'; input.accept = 'image/*'; input.hidden = true;
            input.dataset.mangaUpload = key;
            box.appendChild(input);
            const upload = button(title, () => input.click());
            const clear = button('移除', () => {
                set(key, '');
                if (key === 'storyboard') { set('panels_json', ''); resetCheck(); }
                refresh();
                status.textContent = '已移除图片，将按剩余输入自动选择模式。';
            });
            const label = document.createElement('div');
            label.style.cssText = 'font-size:12px;color:#bbb;word-break:break-all';
            const preview = document.createElement('img');
            preview.style.cssText = 'max-width:100%;max-height:100px;object-fit:contain;margin-top:6px';
            box.append(upload, clear, label, preview);
            panels[key] = { label, preview, clear };
            input.addEventListener('change', async () => {
                const file = input.files?.[0]; if (!file) return;
                upload.disabled = true;
                try {
                    const body = new FormData();
                    body.append('image', file); body.append('subfolder', 'MangaUnified'); body.append('type', 'input');
                    const response = await api.fetchApi('/upload/image', { method: 'POST', body });
                    if (!response.ok) throw new Error(await response.text());
                    const saved = await response.json();
                    set(key, saved.subfolder ? saved.subfolder + '/' + saved.name : saved.name);
                    if (key === 'storyboard') { set('panels_json', ''); resetCheck(); }
                    refresh();
                    status.textContent = key === 'storyboard' ? '分镜已上传，开始检查格框。' : '参考图已上传。可继续上传分镜，或点击生成。';
                    if (key === 'storyboard') await queue(false);
                } catch (error) { status.textContent = '上传失败：' + error.message; }
                finally { upload.disabled = false; input.value = ''; }
            });
            uploads.appendChild(box);
        }
        const check = button('检查 / 重新检查分镜框', () => queue(false));
        const confirm = button('确认格框并生成', () => queue(true));
        confirm.dataset.mangaAction = 'confirm';
        const generate = button('生成漫画（自动判断）', () => queue(Boolean(widget('storyboard').value && widget('confirmed_layout').value)));
        generate.dataset.mangaAction = 'generate';
        root.append(check, confirm, generate, status);
        const dom = node.addDOMWidget('manga_unified_uploads', 'manga_unified_uploads', root, {
            serialize: false, hideOnZoom: false, getValue: () => '', setValue: () => {},
        });
        dom.serialize = false;
        dom.computeSize = () => [520, 465];
        node.widgets.splice(node.widgets.indexOf(dom), 1);
        node.widgets.splice(1, 0, dom);
        for (const type of ['pointerdown', 'mousedown', 'wheel', 'dblclick', 'contextmenu']) {
            root.addEventListener(type, event => event.stopPropagation(), type === 'wheel' ? { passive: true } : undefined);
        }
        const previous = node.onExecuted;
        node.onExecuted = function (message) {
            previous?.apply(this, arguments);
            const result = message?.manga_panel_check?.[0];
            if (result) {
                set('panels_json', result.panels_json);
                set('confirmed_layout', result.signature);
                set('stage', '自动判断（分镜先检查）');
                status.textContent = `检查完成：${result.panel_count} 个区域。核对右侧编号预览；正确后点击“确认格框并生成”。修改坐标后请重新检查。`;
                refresh();
            } else if (message?.manga_route) {
                status.textContent = '当前生成方式：' + { auto: '自动分镜', photo: '参考图转绘', storyboard: '按确认分镜生成' }[message.manga_route[0]];
            }
        };
        const configured = node.onConfigure;
        node.onConfigure = function () { configured?.apply(this, arguments); setTimeout(refresh, 0); };
        for (const name of ['panels_json', 'border_inset']) {
            const w = widget(name), callback = w.callback;
            w.callback = function () { callback?.apply(this, arguments); resetCheck(); refresh(); };
        }
        refresh();
        node.size = [560, Math.max(node.size[1], 1100)];
    },
});
