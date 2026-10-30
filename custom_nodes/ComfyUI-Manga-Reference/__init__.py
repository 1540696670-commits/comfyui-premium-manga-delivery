import json
import cv2
import numpy as np
import torch
import torch.nn.functional as F
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


class MangaReferenceExtension(ComfyExtension):
    async def get_node_list(self):
        return [MangaReferenceResize, MangaPanelExtract, MangaPanelCompose]


async def comfy_entrypoint():
    return MangaReferenceExtension()
