import json
import cv2
import numpy as np


def find_panels(rgb):
    h, w = rgb.shape[:2]
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    ink = (gray < 110).astype(np.uint8) * 255
    contours, _ = cv2.findContours(ink, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    candidates = []
    for contour in contours:
        area = abs(cv2.contourArea(contour))
        if area < w * h * 0.015 or area > w * h * 0.97:
            continue
        polygon = cv2.approxPolyDP(contour, 0.012 * cv2.arcLength(contour, True), True)
        if len(polygon) != 4 or not cv2.isContourConvex(polygon):
            continue
        x, y, pw, ph = cv2.boundingRect(polygon)
        if pw < w * 0.08 or ph < h * 0.06:
            continue
        candidates.append((area, polygon[:, 0].tolist(), (x, y, pw, ph)))
    selected = []
    for candidate in sorted(candidates, reverse=True):
        _, poly, (x, y, pw, ph) = candidate
        duplicate = False
        for _, _, (sx, sy, sw, sh) in selected:
            overlap = max(0, min(x + pw, sx + sw) - max(x, sx)) * max(0, min(y + ph, sy + sh) - max(y, sy))
            if overlap / min(pw * ph, sw * sh) > 0.88:
                duplicate = True
                break
        if not duplicate:
            selected.append(candidate)
    selected.sort(key=lambda c: (c[2][1] // max(1, h // 30), c[2][0]))
    if not selected:
        raise ValueError('未检测到闭合分镜框。请使用清晰边框，或在 panels_json 中填写矩形/多边形坐标后重试。')
    return [dict(polygon=poly) for _, poly, _ in selected]


def parse_panels(text, width, height):
    data = json.loads(text)
    source_w, source_h = width, height
    if isinstance(data, dict):
        source_w, source_h = data.get('width', width), data.get('height', height)
        data = data.get('panels', data.get('items'))
    if not isinstance(data, list) or not data:
        raise ValueError('panels_json 需要非空 panels 数组。每格使用 rect:[x1,y1,x2,y2] 或 polygon:[[x,y],...]。')
    panels = []
    for entry in data:
        if 'polygon' in entry:
            poly = entry['polygon']
        else:
            x1, y1, x2, y2 = entry.get('rect', entry.get('bbox'))
            poly = [[x1, y1], [x2, y1], [x2, y2], [x1, y2]]
        poly = [[round(float(x) * width / source_w), round(float(y) * height / source_h)] for x, y in poly]
        if len(poly) < 3 or any(x < 0 or y < 0 or x >= width or y >= height for x, y in poly):
            raise ValueError('分镜坐标超出原图范围，请根据预览修正。坐标从左上角开始，以像素计。')
        panels.append(dict(polygon=poly, prompt=str(entry.get('prompt', entry.get('caption', '')))))
    return panels


def panel_mask(panel, width, height, inset):
    mask = np.zeros((height, width), dtype=np.uint8)
    cv2.fillPoly(mask, [np.array(panel['polygon'], dtype=np.int32)], 255)
    if inset:
        mask = cv2.erode(mask, np.ones((inset * 2 + 1, inset * 2 + 1), dtype=np.uint8))
    return mask


def page_masks(panels, width, height, inset):
    interiors = [panel_mask(p, width, height, inset) for p in panels]
    borders = np.zeros((height, width), np.uint8)
    for panel, interior in zip(panels, interiors):
        borders |= panel_mask(panel, width, height, 0) & ~interior
    return [mask & ~borders for mask in interiors]
