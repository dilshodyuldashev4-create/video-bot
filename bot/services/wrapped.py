"""«Твой 2026»: a shareable year-in-review card (PNG) drawn with Pillow."""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1350
FONT_DIRS = ("/usr/share/fonts/truetype/dejavu", "/usr/share/fonts/dejavu", "/usr/share/fonts/TTF")


def _font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    for d in FONT_DIRS:
        p = Path(d) / name
        if p.exists():
            return ImageFont.truetype(str(p), size)
    return ImageFont.load_default(size)


def _fit(draw: ImageDraw.ImageDraw, text: str, font, width: int) -> str:
    if draw.textlength(text, font=font) <= width:
        return text
    while text and draw.textlength(text + "…", font=font) > width:
        text = text[:-1]
    return text.rstrip() + "…"


def _gradient() -> Image.Image:
    top, bottom = (255, 46, 99), (63, 24, 146)
    img = Image.new("RGB", (W, H))
    px = ImageDraw.Draw(img)
    for y in range(H):
        k = y / (H - 1)
        px.line([(0, y), (W, y)], fill=tuple(int(a + (b - a) * k) for a, b in zip(top, bottom)))
    return img


def render(stats: dict, labels: dict, bot: str, out: Path) -> Path:
    """labels: title, tracks, days, artists, songs (already in the user's language)."""
    img = _gradient()
    d = ImageDraw.Draw(img)
    white, soft = (255, 255, 255), (255, 225, 235)
    x, inner = 80, W - 160

    d.text((x, 80), labels["title"], font=_font(92, True), fill=white)
    d.rounded_rectangle([x, 220, x + 440, 430], 36, outline=white, width=3)
    d.text((x + 30, 235), str(stats["total"]), font=_font(110, True), fill=white)
    d.text((x + 34, 370), labels["tracks"], font=_font(34), fill=soft)
    d.rounded_rectangle([x + 480, 220, W - 80, 430], 36, outline=white, width=3)
    d.text((x + 510, 235), str(stats["days"]), font=_font(110, True), fill=white)
    d.text((x + 514, 370), labels["days"], font=_font(34), fill=soft)

    y = 490
    d.text((x, y), labels["artists"], font=_font(48, True), fill=white)
    y += 75
    f = _font(40)
    for i, (name, count) in enumerate(stats["artists"][:5], 1):
        d.text((x, y), _fit(d, f"{i}. {name}", f, inner - 120), font=f, fill=white)
        d.text((W - 80, y), str(count), font=f, fill=soft, anchor="ra")
        y += 58

    y += 30
    d.text((x, y), labels["songs"], font=_font(48, True), fill=white)
    y += 75
    for i, (title, performer, count) in enumerate(stats["songs"][:5], 1):
        line = f"{i}. {performer} - {title}" if performer else f"{i}. {title}"
        d.text((x, y), _fit(d, line, f, inner - 120), font=f, fill=white)
        d.text((W - 80, y), str(count), font=f, fill=soft, anchor="ra")
        y += 58

    d.text((W // 2, H - 90), f"@{bot}", font=_font(44, True), fill=white, anchor="mm")
    img.save(out, "PNG", optimize=True)
    return out
