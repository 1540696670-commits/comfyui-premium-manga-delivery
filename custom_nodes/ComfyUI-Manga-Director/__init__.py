import json
import re

from comfy_api.latest import ComfyExtension, io
from json_repair import loads as repair_json_loads
from .premium_layout import MODES, compose_premium


SYSTEM = '''You are an expert manga storyboard director. Convert the user's idea into a coherent sequential comic page. Preserve the user's characters, genre, emotional tone, chronological event order and ending. Never assume a duel or fixed cast. When panel count is Auto, choose 4 or 5 panels. Otherwise use the requested count.

Return ONLY these plain-text fields, in English. Do not use JSON or markdown. Repeat the PANEL block for each scene:
TITLE: short title
CAST: consistent character appearances, clothing and distinctive details
SETTING: location, atmosphere and lighting
LAYOUT: splash, diagonal, or inset
PANEL 1
SHOT: specific camera distance, angle and composition
ACTION: visible action, body pose and emotion in this moment
IMPORTANCE: 2
PANEL 2
SHOT: ...
ACTION: ...
IMPORTANCE: 5

Assign importance 5 to ONE key emotional/action scene; supporting panels get 1-3. Design a dramatic editorial manga page, not a regular grid. splash: a tall dominant character scene breaks its background frame, with small eye/hand detail insets and a narrow atmospheric side panel. diagonal: a sweeping action scene with oblique borders, a readable two-person silhouette, and small reaction cuts. inset: a large cinematic scene with layered close-up inserts and quiet negative space. Choose a layout that serves this story.
Establish the situation, develop it, show the central event, then land an ending. The last panel should show the user's ending. If the idea is one moment, show that moment and its reaction/details rather than inventing a long plot. Give the main scene a clear face, body gesture or interaction; support it with extreme close-ups of eyes, hands, a meaningful prop and environmental details. Avoid repeated portraits. Keep character designs and spatial continuity consistent. Aim for 25-45 English words per ACTION. No coordinates: the compositor handles geometry. No lettering or dialogue unless explicitly requested. No text outside the fields.'''


def parse_plan(text, count):
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.S)
    start, end = text.find('{'), text.rfind('}')
    if start < 0 or end < start:
        raise ValueError('The director did not return JSON.')
    body = text[start:end + 1]
    try:
        plan = json.loads(body)
    except json.JSONDecodeError:
        plan = repair_json_loads(body)
    panels = plan['panels']
    if not isinstance(panels, list) or not 2 <= len(panels) <= 8:
        raise ValueError('Use between 2 and 8 readable panels.')
    if count != 'Auto' and len(panels) != int(count):
        raise ValueError('Use exactly ' + count + ' panels.')
    rectangles = []
    for panel in panels:
        rect = [float(value) for value in panel['rect']]
        if len(rect) != 4:
            raise ValueError('Each rect needs four coordinates.')
        if max(rect) <= 1:
            rect = [value * 1000 for value in rect]
        rect = [max(20, min(980, value)) for value in rect]
        x1, y1, x2, y2 = rect
        if x2 - x1 < 100 or y2 - y1 < 95:
            raise ValueError('A panel is too narrow to read; make it larger.')
        if not str(panel.get('beat', '')).strip():
            raise ValueError('Each panel needs a visible story beat.')
        panel['rect'] = rect
        for other in rectangles:
            overlap = max(0, min(x2, other[2]) - max(x1, other[0])) * max(0, min(y2, other[3]) - max(y1, other[1]))
            area = min((x2 - x1) * (y2 - y1), (other[2] - other[0]) * (other[3] - other[1]))
            if overlap > area * 0.025:
                raise ValueError('Panel rectangles overlap. Separate them with white gutters.')
        rectangles.append(rect)
    return plan


def parse_director_output(text, count):
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.S).replace('**', '').strip()
    if text.startswith('{') or text.startswith('```json'):
        return parse_plan(text, count)

    def field(body, key, default=''):
        match = re.search(r'(?im)^\s*' + key + r'\s*[:：]\s*(.*?)(?=\n\s*[A-Z][A-Z _]{1,20}\s*[:：]|\Z)', body, re.S)
        return match.group(1).strip() if match else default

    matches = list(re.finditer(r'(?im)^\s*(?:#{1,4}\s*)?PANEL\s*(\d+)\s*[:：.\-]?\s*([^\n]*)', text))
    if not 2 <= len(matches) <= 8:
        raise ValueError('Return 3-6 numbered PANEL blocks, each with SHOT and ACTION fields.')
    prefix = text[:matches[0].start()]
    plan = dict(title=field(prefix, 'TITLE', 'Comic'), cast=field(prefix, 'CAST'),
                setting=field(prefix, 'SETTING'), layout=field(prefix, 'LAYOUT', 'splash'), panels=[])
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        body = text[match.end():end]
        # A header may have consumed the following SHOT line through whitespace.
        body = match.group(2) + '\n' + body
        importance = re.search(r'\b([1-5])\b', field(body, 'IMPORTANCE', '2'))
        shot = field(body, 'SHOT', 'Cinematic manga composition')
        action = field(body, 'ACTION', body.strip())
        plan['panels'].append(dict(rect=[20, 20 + index * 960 / len(matches),
                                         980, 20 + (index + 1) * 960 / len(matches) - 16],
                                   shot=shot, beat=action, importance=int(importance.group(1)) if importance else 2))
    return parse_plan(json.dumps(plan, ensure_ascii=False), count)


def refine_page_layout(plan):
    panels = plan['panels']
    # Normalize unused outer margins without changing the director's composition.
    left = min(p['rect'][0] for p in panels)
    top = min(p['rect'][1] for p in panels)
    right = max(p['rect'][2] for p in panels)
    bottom = max(p['rect'][3] for p in panels)
    for panel in panels:
        x1, y1, x2, y2 = panel['rect']
        panel['rect'] = [20 + (x1 - left) * 960 / (right - left),
                         20 + (y1 - top) * 960 / (bottom - top),
                         20 + (x2 - left) * 960 / (right - left),
                         20 + (y2 - top) * 960 / (bottom - top)]
    areas = [(p['rect'][2] - p['rect'][0]) * (p['rect'][3] - p['rect'][1]) for p in panels]
    if max(areas) >= 300000 and max(areas) >= min(areas) * 1.6:
        return plan

    # Weak LLM geometry often consists of equal strips. Pack consecutive beats
    # into rows around the story's focal scene, preserving reading order.
    scores = [float(p.get('importance', 2)) for p in panels]
    focus = max(range(len(panels)), key=lambda i: (scores[i], i))
    rows = []
    for indices in [list(range(focus)), [focus], list(range(focus + 1, len(panels)))]:
        if indices == [focus]:
            rows.append(indices)
        else:
            if len(indices) % 2:
                rows.append(indices[:1])
                indices = indices[1:]
            rows.extend(indices[i:i + 2] for i in range(0, len(indices), 2))
    gap = 16
    usable = 960 - gap * (len(rows) - 1)
    weights = [sum(areas[i] for i in row) ** 0.5 for row in rows]
    main_row = next(i for i, row in enumerate(rows) if row == [focus])
    other_weight = sum(weights) - weights[main_row]
    heights = [usable * 0.56 * weight / other_weight if i != main_row else usable * 0.44
               for i, weight in enumerate(weights)]
    y = 20
    for row, height in zip(rows, heights):
        aspects = [(panels[i]['rect'][2] - panels[i]['rect'][0]) /
                   (panels[i]['rect'][3] - panels[i]['rect'][1]) for i in row]
        widths = [max(0.75, min(1.35, aspect ** 0.25)) for aspect in aspects]
        available = 960 - gap * (len(row) - 1)
        x = 20
        for index, weight in zip(row, widths):
            width = available * weight / sum(widths)
            panels[index]['rect'] = [x, y, x + width, y + height]
            x += width + gap
        y += height + gap
    return plan


class MangaStoryboardDirector(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='MangaStoryboardDirector',
            display_name='漫画导演 · 提示词自动分镜',
            category='Manga/自动分镜',
            description='用本地语言模型根据任意故事设计角色、镜头与不等大的漫画分镜。没有固定故事或固定打斗布局。',
            inputs=[
                io.Clip.Input('clip'),
                io.String.Input('story', display_name='故事提示词', multiline=True, default='雨后的街角，一只小狐狸捡到女孩遗落的红伞，追过长街将伞送还；女孩蹲下轻轻抱住它。温暖治愈。'),
                io.Combo.Input('panels', display_name='分镜格数', options=['Auto', '3', '4', '5', '6'], default='Auto'),
                io.Combo.Input('style', display_name='画风', options=['黑白精细漫画', '彩色电影感漫画', '水彩治愈漫画'], default='黑白精细漫画'),
                io.String.Input('mood', display_name='情绪与导演要求', default='遵循故事本身的情绪，人物表情细腻，叙事清楚'),
                io.Int.Input('width', display_name='画布宽度', default=768, min=256, max=2048, step=16),
                io.Int.Input('height', display_name='画布高度', default=1152, min=256, max=2048, step=16),
                io.Int.Input('seed', display_name='导演种子', default=42, min=0, max=0xffffffffffffffff),
                io.Combo.Input('composition', display_name='高级分镜构图', options=MODES,
                               default='主视觉破框（参考图）', optional=True),
            ],
            outputs=[io.String.Output('layout_draft'), io.String.Output('storyboard')],
        )

    @classmethod
    def execute(cls, clip, story, panels, style, mood, width, height, seed,
                composition='主视觉破框（参考图）'):
        request = (f'Page: {width}x{height}. Panel count: {panels}. Mood: {mood}. '
                   f'Composition: {composition}.\nUSER STORY:\n{story}\n\n'
                   '导演要求：严格按故事发生的先后顺序。最后一格必须是故事的结尾，不能把前面的动作放到最后。'
                   '自动格数选择4或5格。用小格铺垫，用明显更大的主格展示关键动作或情绪高潮。关键情绪用特写，环境变化用远景，结尾镜头服从故事。'
                   '一个大主视觉，配合眼睛/手/道具等局部特写、窄长环境画格与收尾镜头。人物允许突破主格边框。不要等宽横条或每格都重复人像。'
                   '严格使用TITLE/CAST/SETTING/PANEL/SHOT/ACTION/IMPORTANCE的纯文本格式，不要JSON，不要解释，描述用英文。')
        last_error = ''
        for attempt in range(2):
            prompt = request
            if attempt:
                prompt += '\nYour previous outline had this problem. Recreate all the plain-text PANEL blocks: ' + last_error
            tokens = clip.tokenize(prompt, min_length=1, thinking=False, system_prompt=SYSTEM)
            ids = clip.generate(tokens, do_sample=True, max_length=1500, temperature=0.6,
                                top_k=40, top_p=0.9, min_p=0.05, repetition_penalty=1.05,
                                seed=seed + attempt, mtp=False)
            result = clip.decode(ids).strip()
            try:
                plan = parse_director_output(result, panels)
                if composition == '电影叙事（常规）':
                    plan = refine_page_layout(plan)
                break
            except (ValueError, KeyError, TypeError) as error:
                last_error = str(error)
        else:
            raise ValueError('自动分镜未返回有效布局，请更换导演 seed 后重试。详情：' + last_error)

        styles = {
            '黑白精细漫画': 'Finished premium black-and-white manga, crisp expressive ink lines, fine crosshatching, deep solid blacks, pure white paper, no color, no gray wash.',
            '彩色电影感漫画': 'Finished premium full-color cinematic comic, sophisticated color scripting, expressive ink contours, carefully controlled lighting and color contrast.',
            '水彩治愈漫画': 'Finished delicate watercolor comic, soft luminous colors, elegant hand-drawn outlines, subtle paper texture, gentle atmospheric light.',
        }
        if composition != '电影叙事（常规）':
            draft, selected_mode, focal = compose_premium(plan, composition, width, height, seed, styles[style])
            shots = [str(plan.get('title', '漫画分镜')), f'构图：{selected_mode}',
                     f'主视觉：镜头 {focal + 1}，人物破框与背景分层', '',
                     '角色设定 / Cast', str(plan.get('cast', '')), '']
            for index, panel in enumerate(plan['panels'], 1):
                shots.extend([f"镜头 {index} · {panel.get('shot', '')}", str(panel['beat']), ''])
            return io.NodeOutput(json.dumps(draft, ensure_ascii=False), '\n'.join(shots))
        caption = (styles[style] + ' A single coherent sequential manga page. '
                   'Clean white gutters and precise black panel borders. Strong visual hierarchy, '
                   'varied camera distances, readable silhouettes, cinematic staging. '
                   'Maintain the SAME character appearances throughout all panels. '
                   f"Character designs: {plan.get('cast', '')}. Setting: {plan.get('setting', '')}. "
                   'Read panels top-to-bottom, left-to-right. No extra panels or repeated portraits. '
                   'No writing, panel numbers, speech bubbles or watermarks except explicitly supplied text.')
        elements = []
        shots = [str(plan.get('title', '漫画分镜')), '', '角色设定 / Cast', str(plan.get('cast', '')), '']
        for index, panel in enumerate(plan['panels'], 1):
            x1, y1, x2, y2 = panel['rect']
            box = [round(x1 * width / 1000), round(y1 * height / 1000), round(x2 * width / 1000), round(y2 * height / 1000)]
            description = f"Panel {index}, bordered manga panel. {panel.get('shot', '')}. {panel['beat']}. Consistent character designs as specified for the whole page."
            elements.append(dict(label='object', bbox=box, caption=description))
            shots.extend([f"镜头 {index} · {panel.get('shot', '')}", str(panel['beat']), ''])
            if panel.get('text'):
                tx1, ty1 = box[0] + 8, box[1] + 8
                elements.append(dict(label='text', bbox=[tx1, ty1, min(box[2] - 8, tx1 + width // 5), min(box[3] - 8, ty1 + height // 12)], text=str(panel['text']), caption='Small legible lettering in a white speech balloon.'))
        draft = dict(width=width, height=height, bbox_coord_space='abs', bbox_format='xyxy',
                     summary=dict(meta=['comic'], canvas='multi_panel', caption=caption), items=elements)
        return io.NodeOutput(json.dumps(draft, ensure_ascii=False), '\n'.join(shots))


class MangaDirectorExtension(ComfyExtension):
    async def get_node_list(self):
        return [MangaStoryboardDirector]


async def comfy_entrypoint():
    return MangaDirectorExtension()
