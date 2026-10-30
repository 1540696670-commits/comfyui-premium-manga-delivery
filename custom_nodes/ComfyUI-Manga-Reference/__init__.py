import json
import hashlib
from pathlib import Path
import cv2
import numpy as np
import torch
import torch.nn.functional as F
import folder_paths
import nodes
from comfy_execution.graph_utils import GraphBuilder, is_link
from comfy_api.latest import ComfyExtension, io
from .panels import find_panels, parse_panels, page_masks


def resize_image(image, max_side):
    h, w = image.shape[1:3]
    ratio = max_side / max(h, w)
    th, tw = max(64, round(h * ratio / 16) * 16), max(64, round(w * ratio / 16) * 16)
    return F.interpolate(image.movedim(-1, 1), size=(th, tw), mode='bilinear', align_corners=False).movedim(1, -1)


class MangaReferenceResize(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='MangaReferenceResize', display_name='参考图尺寸 · 保持完整画面', category='manga/reference',
            inputs=[io.Image.Input('image'), io.Int.Input('max_side', default=768, min=256, max=2048, step=16)],
            outputs=[io.Image.Output()])

    @classmethod
    def execute(cls, image, max_side):
        return io.NodeOutput(resize_image(image, max_side))


class MangaPanelExtract(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='MangaPanelExtract', display_name='上传分镜 · 检测与逐格裁切', category='manga/reference',
            description='先检查编号预览和导出的坐标。自动检测不保证正确；复杂叠框/斜框请填写 panels_json，合成会严格使用确认后的多边形。',
            inputs=[io.Image.Input('storyboard'),
                io.String.Input('panels_json', default='', multiline=True, tooltip='留空自动检测。手动格式：{"panels":[{"rect":[20,20,360,520],"prompt":"close-up of a woman"}]}'),
                io.String.Input('style_prompt', default='Redraw this exact storyboard shot as finished black-and-white manga. Preserve the same subject, pose, viewpoint, camera distance, clothing and object positions. Refine ink lines and crosshatching. No additional panels, no lettering.', multiline=True),
                io.Int.Input('panel_max_side', default=512, min=256, max=1536, step=16),
                io.Int.Input('border_inset', default=4, min=0, max=32)],
            outputs=[io.Image.Output(display_name='逐格原图', is_output_list=True),
                     io.String.Output(display_name='逐格指令', is_output_list=True),
                     io.String.Output(display_name='合成信息'), io.Image.Output(display_name='编号预览'),
                     io.String.Output(display_name='检测坐标_可复制修改')])

    @classmethod
    def execute(cls, storyboard, panels_json, style_prompt, panel_max_side, border_inset):
        if storyboard.shape[0] != 1:
            raise ValueError('一次请上传一张分镜页。')
        h, w = storyboard.shape[1:3]
        rgb = (storyboard[0, :, :, :3].cpu().numpy().clip(0, 1) * 255).astype(np.uint8)
        panels = parse_panels(panels_json, w, h) if panels_json.strip() else find_panels(rgb)
        images, prompts = [], []
        preview = rgb.copy()
        for index, (panel, mask) in enumerate(zip(panels, page_masks(panels, w, h, border_inset))):
            ys, xs = np.where(mask > 0)
            if not len(xs):
                raise ValueError('边框内缩后分镜为空，请减小 border_inset。')
            x1, y1, x2, y2 = int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1
            panel['crop'] = [x1, y1, x2, y2]
            crop = storyboard[:, y1:y2, x1:x2, :3]
            local = torch.from_numpy(mask[y1:y2, x1:x2] > 0).to(crop.device)[None, :, :, None]
            crop = torch.where(local, crop, torch.ones_like(crop))
            images.append(resize_image(crop, panel_max_side))
            prompts.append(style_prompt + (' This panel: ' + panel['prompt'] if panel.get('prompt') else ''))
            overlay = np.array([125, 75, 220], dtype=np.float32)
            preview[mask > 0] = (preview[mask > 0] * 0.72 + overlay * 0.28).astype(np.uint8)
            cv2.polylines(preview, [np.array(panel['polygon'], np.int32)], True, (130, 60, 220), 2)
            cv2.putText(preview, str(index + 1), (x1 + 8, y1 + 30), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (240, 40, 70), 2)
        exported = json.dumps(dict(width=w, height=h, panels=[{k: v for k, v in p.items() if k != 'crop'} for p in panels]), ensure_ascii=False, indent=2)
        packet = json.dumps(dict(width=w, height=h, inset=border_inset, panels=panels), ensure_ascii=False)
        return io.NodeOutput(images, prompts, packet, torch.from_numpy(preview.astype(np.float32) / 255)[None], exported)


class MangaPanelCompose(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='MangaPanelCompose', display_name='逐格合成 · 锁定原分镜边框', category='manga/reference', is_input_list=True,
            inputs=[io.Image.Input('original'), io.Image.Input('generated_panels'), io.String.Input('composition')],
            outputs=[io.Image.Output(display_name='原尺寸漫画页'), io.Mask.Output(display_name='实际改绘区域')])

    @classmethod
    def execute(cls, original, generated_panels, composition):
        source = original[0]
        packet = json.loads(composition[0])
        panels = packet['panels']
        if len(generated_panels) != len(panels):
            raise ValueError('生成图数量与分镜数量不一致，请连接完整的逐格采样输出，不要手动拼接或丢弃列表项。')
        h, w = source.shape[1:3]
        if (w, h) != (packet['width'], packet['height']):
            raise ValueError('原分镜页尺寸改变，请重新运行裁切节点。')
        result = source[:, :, :, :3].clone()
        union = np.zeros((h, w), np.uint8)
        for panel, generated, mask in zip(panels, generated_panels, page_masks(panels, w, h, packet['inset'])):
            x1, y1, x2, y2 = panel['crop']
            if generated.shape[0] != 1:
                raise ValueError('每格 batch 请设为 1；需要多页时使用队列。')
            tile = F.interpolate(generated.movedim(-1, 1), size=(y2-y1, x2-x1), mode='bilinear', align_corners=False).movedim(1, -1)
            local = torch.from_numpy(mask[y1:y2, x1:x2] > 0).to(result.device)[None, :, :, None]
            result[:, y1:y2, x1:x2] = torch.where(local, tile.to(result.device), result[:, y1:y2, x1:x2])
            union = np.maximum(union, mask)
        return io.NodeOutput(result, torch.from_numpy(union.astype(np.float32) / 255)[None])


def uploaded_path(name):
    root = Path(folder_paths.get_input_directory()).resolve()
    path = Path(folder_paths.get_annotated_filepath(name)).resolve()
    if root not in path.parents or not path.is_file():
        raise ValueError('上传文件不存在或不在 input 目录内，请通过上传按钮重新选择。')
    return path


def file_digest(name):
    if not name:
        return ''
    h = hashlib.sha256()
    with uploaded_path(name).open('rb') as stream:
        while chunk := stream.read(1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


def layout_signature(name, exported, inset):
    canonical = json.dumps(json.loads(exported), sort_keys=True, separators=(',', ':'), ensure_ascii=False)
    return hashlib.sha256((file_digest(name) + canonical + str(inset)).encode()).hexdigest()


class MangaUnifiedComic(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='MangaUnifiedComic', display_name='漫画工作台 · 上传可选，自动判断', category='manga/unified', enable_expand=True, has_intermediate_output=True,
            inputs=[
                io.String.Input('story', default='黑白精细漫画，保留人物特征，画面有情绪张力。', multiline=True),
                io.String.Input('storyboard', default='', tooltip='可选：通过上传按钮选择分镜页。留空不需要占位图片。'),
                io.String.Input('reference', default='', tooltip='可选：参考照片。与分镜同时上传时辅助人物外观。'),
                io.Combo.Input('stage', options=['自动判断（分镜先检查）', '确认格框并生成']),
                io.String.Input('panels_json', default='', multiline=True),
                io.String.Input('confirmed_layout', default=''),
                io.Int.Input('seed', default=42, min=0, max=2**63-1),
                io.Int.Input('steps', default=30, min=1, max=100),
                io.Int.Input('width', default=768, min=256, max=2048, step=16),
                io.Int.Input('height', default=1152, min=256, max=2048, step=16),
                io.Combo.Input('composition', options=['主视觉破框（参考图）', '自动高级构图', '动态斜切', '叠框特写', '电影叙事（常规）']),
                io.Int.Input('reference_max_side', default=768, min=256, max=1536, step=16),
                io.Int.Input('panel_max_side', default=512, min=256, max=1536, step=16),
                io.Int.Input('border_inset', default=4, min=0, max=32),
                io.Float.Input('reference_denoise', default=0.65, min=0.05, max=1.0, step=0.05),
                io.Float.Input('panel_denoise', default=0.4, min=0.05, max=1.0, step=0.05),
            ], outputs=[io.Image.Output(display_name='检查预览 / 漫画成图'), io.String.Output(display_name='处理状态')])

    @classmethod
    def fingerprint_inputs(cls, storyboard='', reference='', **kwargs):
        return (file_digest(storyboard.strip()), file_digest(reference.strip()))

    @classmethod
    def execute(cls, story, storyboard, reference, stage, panels_json, confirmed_layout, seed, steps, width, height, composition,
                reference_max_side, panel_max_side, border_inset, reference_denoise, panel_denoise):
        storyboard, reference = storyboard.strip(), reference.strip()
        if reference:
            uploaded_path(reference)
        if storyboard:
            image = nodes.LoadImage().load_image(str(uploaded_path(storyboard)))[0]
            check = MangaPanelExtract.execute(image, panels_json, '', panel_max_side, border_inset)
            exported = check[4]
            signature = layout_signature(storyboard, exported, border_inset)
            if stage != '确认格框并生成' or confirmed_layout != signature:
                info = dict(signature=signature, panels_json=exported, panel_count=len(check[0]), mode='check')
                status = f'分镜检查：识别到 {len(check[0])} 个绘制区域。请核对编号与坐标，正确后点击“确认格框并生成”。本次没有加载绘图模型。'
                return io.NodeOutput(check[3], status, ui={'manga_panel_check': [info]})
        mode = 'storyboard' if storyboard else 'photo' if reference else 'auto'
        data = json.loads((Path(__file__).parent / 'templates' / (mode + '.json')).read_text('utf-8'))
        save = next(n for n in data.values() if n['class_type'] == 'SaveImage')
        target = save['inputs']['images']
        for n in data.values():
            values = n['inputs']
            if n['class_type'] == 'KSampler':
                values.update(seed=seed, steps=steps)
                if mode != 'auto':
                    values['denoise'] = panel_denoise if storyboard else reference_denoise
            elif n['class_type'] == 'LoadImage':
                values['image'] = storyboard or reference
            elif n['class_type'] == 'MangaStoryboardDirector':
                values.update(story=story, seed=seed, width=width, height=height, composition=composition)
            elif n['class_type'] == 'VMMOSSLayoutStudio':
                values.update(width=width, height=height)
            elif n['class_type'] == 'MangaReferenceResize':
                values['max_side'] = reference_max_side
            elif n['class_type'] == 'MangaPanelExtract':
                values.update(panels_json=exported, panel_max_side=panel_max_side, border_inset=border_inset)
                values['style_prompt'] += ' User instruction (do not print as lettering): ' + story
                if reference:
                    values['style_prompt'] += ' Image 1 determines this panel composition, pose and camera. Image 2 is an appearance reference only; preserve image 1 staging. Borrow character design and clothing details from image 2 where compatible.'
            elif n['class_type'] == 'TextEncodeMOSSImageEdit' and mode == 'photo' and 'negative' not in n.get('_meta', {}).get('title', '').lower():
                if not n['_meta']['title'].startswith('负面'):
                    values['prompt'] += ' User instruction (do not print as lettering): ' + story
        if storyboard and reference:
            data['reference_source'] = dict(class_type='LoadImage', inputs={'image': reference})
            data['reference_scaled'] = dict(class_type='MangaReferenceResize', inputs={'image': ['reference_source', 0], 'max_side': reference_max_side})
            for n in data.values():
                if n['class_type'] == 'TextEncodeMOSSImageEdit':
                    n['inputs']['images.image_1'] = ['reference_scaled', 0]
        builder = GraphBuilder()
        made = {}

        def build(node_id):
            if node_id not in made:
                node = data[node_id]
                inputs = {}
                for name, value in node['inputs'].items():
                    inputs[name] = build(value[0]).out(value[1]) if is_link(value) else value
                made[node_id] = builder.node(node['class_type'], **inputs)
            return made[node_id]

        final = build(target[0]).out(target[1])
        status = {'auto': '没有上传图片：根据故事自动分镜并生成漫画。',
                  'photo': '仅上传参考图：按原图人物与构图转绘为单幅漫画。',
                  'storyboard': '已确认分镜：逐格重绘并原位合成，保留已确认框线。'}[mode]
        if storyboard and reference:
            status += ' 同时使用第二张参考图辅助外观；人物相似度与动作不保证百分百一致。'
        return io.NodeOutput(final, status, expand=builder.finalize(), ui={'manga_route': [mode]})


class MangaReferenceExtension(ComfyExtension):
    async def get_node_list(self):
        return [MangaReferenceResize, MangaPanelExtract, MangaPanelCompose, MangaUnifiedComic]


async def comfy_entrypoint():
    return MangaReferenceExtension()
