"""Narrative-driven hero pages, rather than a stack of equal rectangular rows."""


MODES = ['主视觉破框（参考图）', '自动高级构图', '动态斜切', '叠框特写', '电影叙事（常规）']


def compose_premium(plan, mode, width, height, seed, style):
    panels = plan['panels']
    if mode == '自动高级构图':
        proposed = str(plan.get('layout', 'splash')).lower()
        mode = '动态斜切' if 'diagonal' in proposed else '叠框特写' if 'inset' in proposed else '主视觉破框（参考图）'
    importance = [float(panel.get('importance', 2)) for panel in panels]
    focal = max(range(len(panels)), key=lambda index: (importance[index], index))
    supporting = [index for index in range(len(panels)) if index != focal]
    # The ending remains a wide closing cut when it is not the main scene.
    closing = supporting[-1] if len(supporting) > 1 else None
    details = [index for index in supporting if index != closing]
    mirror = bool(seed % 2)

    if mode == '动态斜切':
        frame = [0.025, 0.19, 0.975, 0.81]
        subject = [0.055, 0.135, 0.955, 0.835]
        detail_slots = [
            ([0.025, 0.025, 0.45, 0.175], 'wide, very shallow eye or weapon-detail inset'),
            ([0.51, 0.025, 0.975, 0.16], 'opposing-angle reaction close-up inset'),
            ([0.025, 0.35, 0.18, 0.70], 'slim vertical impact/detail inset'),
            ([0.80, 0.44, 0.975, 0.75], 'small cropped reaction inset'),
            ([0.025, 0.23, 0.20, 0.33], 'tiny suspense-detail inset'),
        ]
        closing_slot = [0.025, 0.855, 0.975, 0.975]
        border = ('The huge main frame is a slanted trapezoid: its upper border rises from '
                  'lower-left to upper-right and its lower border follows a different diagonal. '
                  'Keep this an actual oblique comic frame, not a level horizontal rectangle.')
        staging = ('Dynamic foreshortened full-body staging appropriate to the event. If two characters '
                   'interact, show both silhouettes and the space between them clearly. The main '
                   'subject, hair, clothing or gesture crosses the diagonal frame at selected points.')
    elif mode == '叠框特写':
        frame = [0.035, 0.095, 0.965, 0.81]
        subject = [0.19, 0.025, 0.94, 0.83]
        detail_slots = [
            ([0.025, 0.025, 0.29, 0.21], 'small extreme close-up inset overlapping the main scene'),
            ([0.025, 0.39, 0.245, 0.70], 'slim vertical meaningful-object or hand inset'),
            ([0.755, 0.035, 0.975, 0.235], 'small contrasting-angle detail inset'),
            ([0.76, 0.51, 0.975, 0.78], 'cropped atmospheric detail inset'),
            ([0.025, 0.24, 0.245, 0.36], 'small silent reaction inset'),
        ]
        closing_slot = [0.025, 0.86, 0.975, 0.975]
        border = ('A large cinematic background frame with smaller white-bordered inset frames layered '
                  'over quiet peripheral areas. A few edges dissolve into white paper. Never cover the main face.')
        staging = ('A large expressive portrait, three-quarter body or clear interaction appropriate to '
                   'the story. Keep face and hands legible. The main subject escapes the background frame '
                   'and overlaps a gutter, while the inset frames remain crisp and readable.')
    else:
        frame = [0.205, 0.065, 0.785, 0.80]
        subject = [0.10, 0.015, 0.795, 0.82]
        detail_slots = [
            ([0.025, 0.025, 0.255, 0.205], 'small upper-corner extreme close-up inset'),
            ([0.81, 0.10, 0.975, 0.79], 'very narrow tall side panel, an elegant close-up or atmospheric motif'),
            ([0.025, 0.25, 0.19, 0.69], 'narrow vertical memory, hand or environmental fragment'),
            ([0.025, 0.705, 0.19, 0.80], 'tiny cropped meaningful-object insert'),
            ([0.81, 0.025, 0.975, 0.085], 'tiny shallow eye-detail inset'),
        ]
        closing_slot = [0.025, 0.845, 0.975, 0.975]
        if len(panels) <= 3:
            frame[2], subject[2] = 0.975, 0.975
        border = ('A tall dominant central background frame, a small upper-corner detail inset, '
                  'a narrow vertical side panel when present, and a low wide closing cut. '
                  'This is an asymmetric hero page, not horizontal tiers or an equal grid.')
        staging = ('An oversized expressive portrait or three-quarter/full-body subject appropriate '
                   'to the event. The top of the head, hair, hat, clothing or a gesture BREAKS OUT '
                   'above and beside the central background frame. Long flowing shapes or directed '
                   'gestures connect the page through an S-shaped visual flow. Keep the face unobscured.')

    def pixel_box(rect):
        x1, y1, x2, y2 = rect
        if mirror:
            x1, x2 = 1 - x2, 1 - x1
        return [round(x1 * width), round(y1 * height), round(x2 * width), round(y2 * height)]

    focus = panels[focal]
    caption = (style + ' A finished high-impact editorial manga page with an asymmetric splash composition. '
               'ONE dominant hero image fills roughly 55-70 percent of the visual page. '
               'Small supporting frames are deliberately much smaller and reveal cropped details, '
               'not competing repeated portraits. ' + border + ' ' + staging + ' '
               'The main background and the foreground character overlay belong to the SAME scene, '
               'not two separate panels. Selected overlapping boxes are intentional frame-breaking layers. '
               'Preserve clean white gutters around secondary panels. Use dark/light mass balance, '
               'negative space and gaze direction to guide the eye between the hero and inserts. '
               f"Consistent cast: {plan.get('cast', '')}. Setting: {plan.get('setting', '')}. "
               'Do not draw a uniform grid, three/four equal horizontal bands, panel numbers, random '
               'writing, speech balloons, watermarks or lettering. Do not duplicate the main character '
               'inside the same main scene. Supporting views are inset memories or close-ups.')
    elements = [dict(label='object', bbox=pixel_box(frame), caption=(
        'MAIN SCENE BACKGROUND FRAME ONLY. ' + border + ' '
        f"Environment: {plan.get('setting', '')}. "
        'Architecture, atmosphere and lighting surround and support the foreground subject. '
        'Leave space for the main foreground cast. Do not put another portrait in this background.'))]
    for slot, index in enumerate(details):
        rect, role = detail_slots[min(slot, len(detail_slots) - 1)]
        panel = panels[index]
        elements.append(dict(label='object', bbox=pixel_box(rect), caption=(
            role + ', thin black border and a clean white rim. '
            f"Story moment: {panel['beat']}. Camera idea: {panel.get('shot', '')}. "
            'Adapt this moment to the tiny frame: crop to eyes, fingers, a significant prop, a '
            'silhouette or a small environmental fragment. Do not squeeze a full scene or another '
            'full-body portrait into a tiny inset. Keep continuity with the main cast.')))
    if closing is not None:
        panel = panels[closing]
        elements.append(dict(label='object', bbox=pixel_box(closing_slot), caption=(
            'Low, wide closing manga panel with a thin black border, separated by a clean white gutter. '
            f"{panel.get('shot', '')}. {panel['beat']}. "
            'Use a deliberate cinematic crop: hands with a meaningful object, an environmental '
            'silhouette, or a quiet ending as appropriate to the story. No repeated large face.')))
    elements.append(dict(label='character', bbox=pixel_box(subject), caption=(
        'THE SINGLE DOMINANT FOREGROUND CAST OF THE MAIN SCENE. '
        f"Character design: {plan.get('cast', '')}. "
        f"Peak story moment: {focus['beat']}. {focus.get('shot', '')}. " + staging + ' '
        'An expressive face, a readable gesture and beautiful detailed rendering carry the emotional '
        'focus. This foreground drawing overlaps the central background frame and selected gutters; '
        'it is NOT enclosed inside a second smaller rectangular portrait. Keep supporting insets visible.')))
    draft = dict(width=width, height=height, bbox_coord_space='abs', bbox_format='xyxy',
                 summary=dict(meta=['comic'], canvas='multi_panel', caption=caption), items=elements)
    return draft, mode, focal
