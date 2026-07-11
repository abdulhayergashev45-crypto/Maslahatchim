"""AI tuzgan reja (JSON) asosida chiroyli dizaynli .pptx fayl yaratish."""

from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE

NAVY = RGBColor(0x1B, 0x2A, 0x4A)
NAVY_DARK = RGBColor(0x11, 0x1A, 0x30)
GOLD = RGBColor(0xC9, 0xA2, 0x27)
LIGHT_BG = RGBColor(0xF3, 0xF4, 0xF7)
TEXT_DARK = RGBColor(0x1E, 0x25, 0x37)
TEXT_GRAY = RGBColor(0x5B, 0x64, 0x78)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)

SLIDE_W = Inches(13.333)
SLIDE_H = Inches(7.5)


def _set_bg(slide, color):
    fill = slide.background.fill
    fill.solid()
    fill.fore_color.rgb = color


def _rect(slide, x, y, w, h, color, line=False):
    shape = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, x, y, w, h)
    shape.fill.solid()
    shape.fill.fore_color.rgb = color
    if not line:
        shape.line.fill.background()
    else:
        shape.line.color.rgb = color
    shape.shadow.inherit = False
    return shape


def _text(slide, x, y, w, h, text, size, color, bold=False, italic=False,
          align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP, font="Calibri"):
    box = slide.shapes.add_textbox(x, y, w, h)
    tf = box.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    tf.margin_left = 0
    tf.margin_right = 0
    tf.margin_top = 0
    tf.margin_bottom = 0
    p = tf.paragraphs[0]
    p.alignment = align
    run = p.add_run()
    run.text = text
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.italic = italic
    run.font.color.rgb = color
    run.font.name = font
    return box


def _bullets(slide, x, y, w, h, items, size, color, font="Calibri", space_after=10):
    box = slide.shapes.add_textbox(x, y, w, h)
    tf = box.text_frame
    tf.word_wrap = True
    tf.margin_left = 0
    tf.margin_right = 0
    for i, item in enumerate(items):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.text = "•  " + item
        p.space_after = Pt(space_after)
        for run in p.runs:
            run.font.size = Pt(size)
            run.font.color.rgb = color
            run.font.name = font
    return box


def _title_slide(prs, title, subtitle):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    _set_bg(slide, NAVY)
    _rect(slide, Inches(-2.2), Inches(5.6), Inches(5), Inches(5), NAVY_DARK)
    _text(slide, Inches(0.85), Inches(2.9), Inches(11.5), Inches(1.4), title,
          44, WHITE, bold=True, font="Cambria")
    _rect(slide, Inches(0.87), Inches(4.05), Inches(1.4), Pt(3), GOLD)
    _text(slide, Inches(0.85), Inches(4.25), Inches(10), Inches(0.6), subtitle,
          18, RGBColor(0xC7, 0xCE, 0xDF))
    _text(slide, Inches(0.85), Inches(6.7), Inches(10), Inches(0.4),
          "Abituriyentlar uchun avtomatik yaratilgan taqdimot", 11,
          RGBColor(0x8C, 0x96, 0xAC))


def _content_slide(prs, idx, title, bullets):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    _set_bg(slide, WHITE)
    _text(slide, Inches(0.85), Inches(0.5), Inches(0.6), Inches(0.4), f"{idx:02d}",
          13, GOLD, bold=True, font="Calibri")
    _text(slide, Inches(0.85), Inches(0.85), Inches(11.5), Inches(0.7), title,
          28, NAVY, bold=True, font="Cambria")
    _rect(slide, Inches(0.85), Inches(1.55), Inches(11.63), Emu(1), LIGHT_BG)
    _bullets(slide, Inches(0.95), Inches(2.0), Inches(11.4), Inches(4.8),
              bullets, 16, TEXT_DARK)


def _conclusion_slide(prs, title, bullets):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    _set_bg(slide, NAVY)
    _rect(slide, Inches(10.6), Inches(5.6), Inches(5), Inches(5), NAVY_DARK)
    _text(slide, Inches(0.85), Inches(0.6), Inches(9), Inches(0.7), title,
          32, WHITE, bold=True, font="Cambria")
    y = 1.7
    for i, item in enumerate(bullets, start=1):
        _rect(slide, Inches(0.85), Inches(y), Inches(0.5), Inches(0.5), GOLD)
        _text(slide, Inches(0.85), Inches(y), Inches(0.5), Inches(0.5), str(i),
              18, NAVY_DARK, bold=True, align=PP_ALIGN.CENTER,
              anchor=MSO_ANCHOR.MIDDLE, font="Cambria")
        _text(slide, Inches(1.6), Inches(y), Inches(10.5), Inches(0.6), item,
              15, WHITE, anchor=MSO_ANCHOR.MIDDLE)
        y += 0.85


def build_presentation(plan: dict, output_path: str) -> str:
    """
    plan — ai_utils.generate_slide_plan() natijasi (dict).
    output_path — yakuniy .pptx fayl yo'li.
    """
    prs = Presentation()
    prs.slide_width = SLIDE_W
    prs.slide_height = SLIDE_H

    slides = plan.get("slides", [])
    content_idx = 1

    for item in slides:
        s_type = item.get("type", "content")
        title = item.get("title", "")

        if s_type == "title":
            _title_slide(prs, title or plan.get("deck_title", ""),
                         item.get("subtitle") or plan.get("deck_subtitle", ""))
        elif s_type == "conclusion":
            _conclusion_slide(prs, title or "Xulosa", item.get("bullets", []))
        else:
            _content_slide(prs, content_idx, title, item.get("bullets", []))
            content_idx += 1

    prs.save(output_path)
    return output_path
