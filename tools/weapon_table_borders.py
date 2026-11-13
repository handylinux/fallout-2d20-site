"""Keep copied source tables inside the content column and draw visible frames."""
import pymupdf
import weapon2pdf as w

BORDER_WIDTH = 0.7


def table_boxes(page, top, bottom=807):
    """Identify adjacent filled cell rectangles as separate table blocks.

    Source pages contain selectable vector cells; only black or paper/orange
    table fills in the clipped region are considered. Headings without tables
    intentionally return no boxes.
    """
    cells = []
    for drawing in page.get_drawings():
        rect = drawing['rect']
        fill = drawing.get('fill')
        if not fill or rect.y0 < top or rect.y1 > bottom + 1:
            continue
        dark = max(fill[:3]) < .1
        beige_or_orange = fill[0] > .94 and .65 < fill[1] < .96 and .35 < fill[2] < .9
        if (dark or beige_or_orange) and 6 <= rect.height < 150 and rect.width >= 10 and 30 <= rect.x0 < 570 and rect.x1 <= 570:
            cells.append(rect)
    groups = []
    for rect in sorted(cells, key=lambda r: r.y0):
        if not groups or rect.y0 > groups[-1].y1 + 1.5:
            groups.append(pymupdf.Rect(rect))
        else:
            groups[-1] |= rect
    return groups


def place_source_block(target_page, source, source_index, clip, target_top, target_bottom=807):
    """Copy source vector content proportionally, frame tables inside margins."""
    source_page = source[source_index]
    boxes = table_boxes(source_page, clip.y0, clip.y1)
    scale = min(1.0, (target_bottom - target_top) / clip.height)
    if boxes:
        bounds = pymupdf.Rect(boxes[0])
        for box in boxes[1:]:
            bounds |= box
        scale = min(scale, (w.CONTENT_W - BORDER_WIDTH) / bounds.width)
        x = w.MARGIN_L + BORDER_WIDTH / 2 - (bounds.x0 - clip.x0) * scale
    else:
        x = (w.PAGE_W - clip.width * scale) / 2
    y = target_bottom - clip.height * scale
    destination = pymupdf.Rect(x, y, x + clip.width * scale, target_bottom)
    target_page.show_pdf_page(destination, source, source_index, clip=clip, keep_proportion=True)
    for box in boxes:
        rect = pymupdf.Rect(x + (box.x0 - clip.x0) * scale,
                            y + (box.y0 - clip.y0) * scale,
                            x + (box.x1 - clip.x0) * scale,
                            y + (box.y1 - clip.y0) * scale)
        # Keep the entire stroke within the content column.
        rect.x0 = max(rect.x0, w.MARGIN_L + BORDER_WIDTH / 2)
        rect.x1 = min(rect.x1, w.CONTENT_R - BORDER_WIDTH / 2)
        target_page.draw_rect(rect, color=(0, 0, 0), fill=None, width=BORDER_WIDTH, overlay=True)
    return boxes


def append_reference_page(result, original, source_number, page_number):
    """Reproduce a source reference page with in-margin proportional tables."""
    page = result.new_page(width=w.PAGE_W, height=w.PAGE_H)
    x, by, width, height = w.paper_placement()
    page.insert_image(pymupdf.Rect(x, w.PAGE_H - by - height, x + width, w.PAGE_H - by), filename=w.PAPER)
    src = original[source_number - 1]
    clip = pymupdf.Rect(0, 0, src.rect.width, 807)
    boxes = place_source_block(page, original, source_number - 1, clip, target_top=0, target_bottom=807)
    if not boxes:
        raise ValueError(f'Страница {source_number}: не найдены таблицы для рамки')
    fontfile = str(__import__('pathlib').Path(w.FONT_DIR) / 'Carlito-Regular.ttf')
    font = pymupdf.Font(fontfile=fontfile)
    page.insert_font(fontname='frameno', fontfile=fontfile)
    label = str(page_number)
    pos = w.MARGIN_L + 2.57 if page_number % 2 == 0 else w.CONTENT_R - 2.57 - font.text_length(label, fontsize=9.96)
    page.insert_text((pos, w.PAGE_NUMBER_TOP + 9.96 * .75), label, fontname='frameno', fontsize=9.96)
