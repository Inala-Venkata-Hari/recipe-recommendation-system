"""Convert the existing DSF HTML slide deck to an editable PowerPoint.
Run: python presentations/build_pptx.py
Dependency: python-pptx
"""
from html.parser import HTMLParser
from pathlib import Path
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "dsf_smart_cart_presentation.html"
TARGET = ROOT / "dsf_smart_cart_presentation.pptx"

class SlideParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.slides = []
        self.current = None
        self.field = None
        self.buffer = []
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "section" and "slide" in attrs.get("class", "").split():
            self.current = {"eyebrow": "", "title": "", "bullets": []}
        if self.current is not None and (tag in ("h1", "li") or (tag == "div" and "eyebrow" in attrs.get("class", "").split())):
            self.field = "title" if tag == "h1" else "bullet" if tag == "li" else "eyebrow"
            self.buffer = []
    def handle_data(self, data):
        if self.field is not None:
            self.buffer.append(data)
    def handle_endtag(self, tag):
        if self.field is not None and (tag in ("h1", "li", "div")):
            value = "".join(self.buffer).strip()
            if self.field == "bullet":
                self.current["bullets"].append(value)
            else:
                self.current[self.field] = value
            self.field = None
        if tag == "section" and self.current is not None:
            self.slides.append(self.current)
            self.current = None

def main():
    parser = SlideParser()
    parser.feed(SOURCE.read_text(encoding="utf-8"))
    if not parser.slides:
        raise ValueError("No slides found in HTML source")
    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
    bg = RGBColor(8, 23, 36)
    white = RGBColor(237, 246, 255)
    teal = RGBColor(98, 214, 199)
    muted = RGBColor(145, 169, 184)
    for idx, item in enumerate(parser.slides, 1):
        slide = prs.slides.add_slide(prs.slide_layouts[6])
        slide.background.fill.solid()
        slide.background.fill.fore_color.rgb = bg
        def text_box(x, y, w, h, text, size, color, bold=False):
            box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
            tf = box.text_frame
            tf.word_wrap = True
            tf.text = text
            for p in tf.paragraphs:
                p.font.name = "Aptos"
                p.font.size = Pt(size)
                p.font.bold = bold
                p.font.color.rgb = color
            return box
        text_box(0.95, 0.55, 11.5, 0.4, item["eyebrow"].upper(), 13, teal, True)
        text_box(0.95, 1.1, 11.5, 1.25, item["title"], 32 if len(item["title"]) < 65 else 27, white, True)
        bullets = item["bullets"]
        n = len(bullets)
        if n:
            available = 3.95
            row_h = min(0.88, available / n)
            for i, bullet in enumerate(bullets):
                text_box(1.05, 2.65 + i * row_h, 11.2, row_h, "•  " + bullet, 19 if n <= 5 else 16, white)
        text_box(0.95, 7.05, 9.5, 0.3, "DSF · Smart Cart Recipe Recommendation System", 10, muted)
        text_box(12.1, 7.05, 0.5, 0.3, str(idx), 10, muted)
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    prs.save(TARGET)
    print(f"Created {TARGET} with {len(prs.slides)} slides")

if __name__ == "__main__":
    main()
