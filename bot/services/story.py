"""🎬 A 15 s vertical clip for Stories: blurred cover background, the cover, title and a lyric line."""
import re
from collections import Counter
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageOps

from .media import RINGTONE_SECONDS, _run, best_part
from .wrapped import _fit, _font

W, H = 1080, 1920
CLIP_SECONDS = 15


def lyric_line(text: str | None) -> str:
    """The chorus line (the most repeated one of a sensible length), else the first such line."""
    if not text:
        return ""
    lines = [ln.strip() for ln in text.splitlines()]
    lines = [ln for ln in lines if 12 <= len(ln) <= 70 and not re.match(r"^[\[(].*[\])]$", ln)]
    if not lines:
        return ""
    counts = Counter(ln.lower() for ln in lines)
    best, n = counts.most_common(1)[0]
    if n > 1:
        return next(ln for ln in lines if ln.lower() == best)
    return lines[0]


def _wrap(draw: ImageDraw.ImageDraw, text: str, font, width: int, max_lines: int = 3) -> list[str]:
    out, cur = [], ""
    for word in text.split():
        trial = f"{cur} {word}".strip()
        if draw.textlength(trial, font=font) <= width:
            cur = trial
        else:
            if cur:
                out.append(cur)
            cur = word
    if cur:
        out.append(cur)
    if len(out) > max_lines:
        out = out[:max_lines]
        out[-1] = _fit(draw, out[-1] + " …", font, width)
    return out


def render_frame(cover: Path | None, title: str, performer: str, line: str, bot: str, out: Path) -> Path:
    if cover and cover.exists():
        art = Image.open(cover).convert("RGB")
    else:
        art = Image.new("RGB", (800, 800), (63, 24, 146))
    bg = ImageOps.fit(art, (W, H)).filter(ImageFilter.GaussianBlur(40))
    bg = Image.blend(bg, Image.new("RGB", (W, H), (0, 0, 0)), 0.45)
    size = 820
    sq = ImageOps.fit(art, (size, size))
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, size, size], 48, fill=255)
    top = 300
    bg.paste(sq, ((W - size) // 2, top), mask)
    d = ImageDraw.Draw(bg)
    white, soft = (255, 255, 255), (230, 230, 240)
    y = top + size + 70
    d.text((W // 2, y), _fit(d, title, _font(64, True), W - 140), font=_font(64, True), fill=white, anchor="mt")
    y += 90
    if performer:
        d.text((W // 2, y), _fit(d, performer, _font(46), W - 140), font=_font(46), fill=soft, anchor="mt")
        y += 90
    if line:
        f = _font(50, True)
        y += 30
        for row in _wrap(d, f"“{line}”", f, W - 160):
            d.text((W // 2, y), row, font=f, fill=white, anchor="mt")
            y += 68
    d.text((W // 2, H - 140), f"@{bot}", font=_font(42, True), fill=white, anchor="mm")
    bg.save(out, "PNG")
    return out


async def make_clip(src: Path, frame: Path, out: Path) -> Path | None:
    start = await best_part(src, RINGTONE_SECONDS)
    code, _, _ = await _run(
        "ffmpeg", "-v", "error", "-y", "-loop", "1", "-framerate", "25", "-i", str(frame),
        "-ss", f"{start:.1f}", "-t", str(CLIP_SECONDS), "-i", str(src),
        "-map", "0:v", "-map", "1:a", "-t", str(CLIP_SECONDS),
        "-vf", f"fade=t=in:d=0.6,fade=t=out:st={CLIP_SECONDS - 0.8}:d=0.8",
        "-af", f"afade=t=in:d=0.8,afade=t=out:st={CLIP_SECONDS - 1.2}:d=1.2",
        "-c:v", "libx264", "-preset", "veryfast", "-tune", "stillimage", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", str(out), timeout=300)
    return out if code == 0 and out.exists() and out.stat().st_size > 10_000 else None
