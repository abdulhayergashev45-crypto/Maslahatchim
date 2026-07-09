"""
Sahnalar ro'yxatidan animatsion .mp4 video yaratadi:
1. Har bir sahna uchun edge-tts bilan o'zbekcha ovoz generatsiya qilinadi.
2. Ovoz uzunligiga qarab, Pillow bilan so'z-so'z ochiluvchi kadrlar chiziladi.
3. ffmpeg har bir sahnani video+ovozga aylantiradi, so'ng hammasini birlashtiradi.
"""

import asyncio
import math
import os
import random
import shutil
import subprocess
import textwrap

import edge_tts
from PIL import Image, ImageDraw, ImageFont

W, H = 1280, 720
FPS = 12
VOICE = "uz-UZ-MadinaNeural"  # muqobil: uz-UZ-SardorNeural

PALETTE = [
    {"a": (22, 27, 49), "b": (35, 43, 77), "accent": (79, 189, 186)},
    {"a": (27, 23, 48), "b": (43, 33, 68), "accent": (242, 183, 5)},
    {"a": (24, 19, 40), "b": (42, 31, 66), "accent": (232, 99, 124)},
]

FONT_DIR = "/usr/share/fonts/truetype/dejavu"
FONT_BOLD = os.path.join(FONT_DIR, "DejaVuSans-Bold.ttf")
FONT_REGULAR = os.path.join(FONT_DIR, "DejaVuSans.ttf")


def _lerp(c1, c2, t):
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))


def _gradient(w, h, top, bottom):
    img = Image.new("RGB", (w, h), top)
    draw = ImageDraw.Draw(img)
    for y in range(h):
        t = y / h
        draw.line([(0, y), (w, y)], fill=_lerp(top, bottom, t))
    return img


def _lighten(c, amount=0.35):
    return tuple(int(c[i] + (255 - c[i]) * amount) for i in range(3))


def _draw_decorations(img, draw, index, progress, accent):
    """Sekin suzib yuruvchi yulduzcha/doiralar — fonni jonli qiladi."""
    rng = random.Random(index * 97)
    light = _lighten(accent, 0.55)
    for _ in range(9):
        bx = rng.uniform(60, W - 60)
        by0 = rng.uniform(90, H - 90)
        drift = math.sin(progress * math.pi * 2 + bx) * 10
        by = by0 + drift
        size = rng.uniform(4, 11)
        shape = rng.choice(["circle", "star"])
        alpha_layer = Image.new("RGBA", (int(size * 4), int(size * 4)), (0, 0, 0, 0))
        d2 = ImageDraw.Draw(alpha_layer)
        col = (*light, 90)
        if shape == "circle":
            d2.ellipse([0, 0, size * 2, size * 2], fill=col)
        else:
            cx0, cy0, r = size * 2, size * 2, size * 1.6
            pts = []
            for k in range(10):
                ang = math.pi / 2 + k * math.pi / 5
                rad = r if k % 2 == 0 else r * 0.45
                pts.append((cx0 + rad * math.cos(ang), cy0 - rad * math.sin(ang)))
            d2.polygon(pts, fill=col)
        img.paste(alpha_layer, (int(bx), int(by)), alpha_layer)


def _draw_character(img, draw, cx, cy, scale, accent, pose):
    """Sodda, do'stona 'kitobcha' multfilm qahramoni — 3 xil poza bilan."""
    bounce = math.sin(pose["t"] * math.pi * 2) * 6
    cy = cy + bounce
    body_w, body_h = 160 * scale, 190 * scale

    # soya
    draw.ellipse([cx - body_w * 0.55, cy + body_h * 0.55,
                  cx + body_w * 0.55, cy + body_h * 0.65], fill=(0, 0, 0, 60))

    # oyoqlar
    leg_col = _lighten(accent, -0.15) if False else tuple(max(0, c - 40) for c in accent)
    for dx in (-body_w * 0.22, body_w * 0.22):
        draw.line([cx + dx, cy + body_h * 0.35, cx + dx, cy + body_h * 0.62],
                   fill=leg_col, width=int(10 * scale))
        draw.ellipse([cx + dx - 12 * scale, cy + body_h * 0.60,
                      cx + dx + 12 * scale, cy + body_h * 0.68], fill=leg_col)

    # qo'llar (poza bo'yicha)
    arm_col = accent
    aw = int(9 * scale)
    if pose["id"] == 0:  # ikkala qo'l tepada — salomlashadi
        for dx in (-1, 1):
            draw.line([cx + dx * body_w * 0.42, cy - body_h * 0.05,
                       cx + dx * body_w * 0.62, cy - body_h * 0.42], fill=arm_col, width=aw)
            draw.ellipse([cx + dx * body_w * 0.62 - 10, cy - body_h * 0.42 - 10,
                          cx + dx * body_w * 0.62 + 10, cy - body_h * 0.42 + 10], fill=arm_col)
    elif pose["id"] == 1:  # bitta qo'l oldinga — tushuntiradi
        draw.line([cx - body_w * 0.42, cy, cx - body_w * 0.68, cy - body_h * 0.12],
                   fill=arm_col, width=aw)
        draw.ellipse([cx - body_w * 0.68 - 10, cy - body_h * 0.12 - 10,
                      cx - body_w * 0.68 + 10, cy - body_h * 0.12 + 10], fill=arm_col)
        draw.line([cx + body_w * 0.42, cy, cx + body_w * 0.55, cy + body_h * 0.15],
                   fill=arm_col, width=aw)
        draw.ellipse([cx + body_w * 0.55 - 10, cy + body_h * 0.15 - 10,
                      cx + body_w * 0.55 + 10, cy + body_h * 0.15 + 10], fill=arm_col)
    else:  # beliga tirsak — ishonchli turadi
        for dx in (-1, 1):
            draw.line([cx + dx * body_w * 0.42, cy - body_h * 0.02,
                       cx + dx * body_w * 0.55, cy + body_h * 0.18], fill=arm_col, width=aw)
            draw.ellipse([cx + dx * body_w * 0.55 - 10, cy + body_h * 0.18 - 10,
                          cx + dx * body_w * 0.55 + 10, cy + body_h * 0.18 + 10], fill=arm_col)

    # tana (kitobcha)
    draw.rounded_rectangle(
        [cx - body_w / 2, cy - body_h / 2, cx + body_w / 2, cy + body_h / 2],
        radius=body_w * 0.22, fill=accent,
    )
    # "sahifa" yuzi
    face_w, face_h = body_w * 0.72, body_h * 0.55
    draw.rounded_rectangle(
        [cx - face_w / 2, cy - body_h * 0.28, cx + face_w / 2, cy - body_h * 0.28 + face_h],
        radius=face_w * 0.18, fill=(251, 246, 234),
    )
    # markazdagi "muqova chizig'i"
    draw.line([cx, cy - body_h * 0.45, cx, cy + body_h * 0.45],
               fill=tuple(max(0, c - 35) for c in accent), width=int(3 * scale))

    # ko'zlar
    eye_y = cy - body_h * 0.05
    for dx in (-face_w * 0.18, face_w * 0.18):
        r = 13 * scale
        draw.ellipse([cx + dx - r, eye_y - r, cx + dx + r, eye_y + r], fill=(30, 30, 40))
        draw.ellipse([cx + dx - r * 0.35 + 3, eye_y - r * 0.35 - 3,
                      cx + dx + r * 0.35 + 3, eye_y + r * 0.35 - 3], fill=(255, 255, 255))

    # tabassum
    smile_y = cy + body_h * 0.10
    draw.arc([cx - face_w * 0.22, smile_y - 14 * scale, cx + face_w * 0.22, smile_y + 18 * scale],
              start=20, end=160, fill=(30, 30, 40), width=int(4 * scale))

    # yonoqlar
    for dx in (-face_w * 0.32, face_w * 0.32):
        r = 9 * scale
        blush = Image.new("RGBA", (int(r * 2), int(r * 2)), (0, 0, 0, 0))
        ImageDraw.Draw(blush).ellipse([0, 0, r * 2, r * 2], fill=(232, 99, 124, 90))
        img.paste(blush, (int(cx + dx - r), int(eye_y + 10 - r)), blush)


def _wrap(draw, text, font, max_width):
    words = text.split(" ")
    lines, line = [], ""
    for w in words:
        test = f"{line} {w}".strip()
        if draw.textlength(test, font=font) > max_width and line:
            lines.append(line)
            line = w
        else:
            line = test
    if line:
        lines.append(line)
    return lines


def _draw_frame(scene, index, total, progress, palette):
    img = _gradient(W, H, palette["a"], palette["b"])
    draw = ImageDraw.Draw(img)

    # sprocket holes (filmstrip motif)
    hole_color = (255, 255, 255, 40)
    for x in range(30, W - 10, 44):
        draw.ellipse([x - 6, 16, x + 6, 28], fill=(255, 255, 255))
        draw.ellipse([x - 6, H - 28, x + 6, H - 16], fill=(255, 255, 255))
    # dim the sprockets by overlaying semi-transparent layer
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    odraw = ImageDraw.Draw(overlay)
    for x in range(30, W - 10, 44):
        odraw.ellipse([x - 6, 16, x + 6, 28], fill=(255, 255, 255, 55))
        odraw.ellipse([x - 6, H - 28, x + 6, H - 16], fill=(255, 255, 255, 55))
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
    draw = ImageDraw.Draw(img)

    font_mono = ImageFont.truetype(FONT_REGULAR, 20)
    font_heading = ImageFont.truetype(FONT_BOLD, 42)
    font_body = ImageFont.truetype(FONT_REGULAR, 30)
    font_emoji = ImageFont.truetype(FONT_BOLD, 120)

    draw.text((46, 50), f"SAHNA {index + 1} / {total}", font=font_mono,
               fill=(255, 255, 255, 160))

    _draw_decorations(img, draw, index, progress, palette["accent"])

    # multfilm personaji
    pose = {"id": index % 3, "t": progress}
    _draw_character(img, draw, W // 2, int(H * 0.34), 1.15, palette["accent"], pose)

    # sahna raqami — kichik nishon
    badge_r = 22
    bx, by = W // 2 + 95, int(H * 0.34) - 95
    draw.ellipse([bx - badge_r, by - badge_r, bx + badge_r, by + badge_r],
                 fill=(251, 246, 234))
    num_text = str(index + 1)
    nb = draw.textbbox((0, 0), num_text, font=font_heading)
    draw.text((bx - (nb[2] - nb[0]) / 2, by - (nb[3] - nb[1]) / 2 - nb[1]),
               num_text, font=font_heading, fill=palette["accent"])

    # heading
    heading = scene.get("heading", "")
    hb = draw.textbbox((0, 0), heading, font=font_heading)
    draw.text(((W - (hb[2] - hb[0])) / 2, H * 0.56), heading, font=font_heading,
               fill=palette["accent"])

    # body text, word-by-word reveal
    words = scene.get("text", "").split(" ")
    shown = max(1, round(len(words) * min(progress * 1.15, 1)))
    visible = " ".join(words[:shown])
    lines = _wrap(draw, visible, font_body, W * 0.72)
    ty = H * 0.68
    for line in lines:
        lb = draw.textbbox((0, 0), line, font=font_body)
        draw.text(((W - (lb[2] - lb[0])) / 2, ty), line, font=font_body, fill=(251, 246, 234))
        ty += 42

    return img


async def _synthesize(text: str, out_path: str, voice: str = VOICE):
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(out_path)


def _make_silence(out_path: str, duration: float):
    """Ovoz xizmati ishlamay qolganda, shu uzunlikdagi jimlik audio fayl yasaydi."""
    subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono",
        "-t", str(duration), "-q:a", "9", "-acodec", "libmp3lame", out_path,
    ], check=True, capture_output=True)


def _estimate_duration(text: str) -> float:
    words = len(text.split())
    return max(words * 0.42 + 0.9, 3.0)


def _audio_duration(path: str) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrapper=1:nokey=1", path],
        capture_output=True, text=True, check=True,
    )
    return float(result.stdout.strip())


def build_video(scenes, output_path: str, work_dir: str, voice: str = VOICE):
    os.makedirs(work_dir, exist_ok=True)
    scene_videos = []
    narration_failed = False

    for i, scene in enumerate(scenes):
        palette = PALETTE[i % len(PALETTE)]
        audio_path = os.path.join(work_dir, f"scene_{i}.mp3")
        text = scene.get("text", "")

        try:
            asyncio.run(_synthesize(text, audio_path, voice))
            duration = max(_audio_duration(audio_path) + 0.6, 3.0)
        except Exception:
            narration_failed = True
            duration = _estimate_duration(text)
            _make_silence(audio_path, duration)

        frame_dir = os.path.join(work_dir, f"frames_{i}")
        os.makedirs(frame_dir, exist_ok=True)
        n_frames = int(duration * FPS)
        for f in range(n_frames):
            progress = f / max(n_frames - 1, 1)
            frame = _draw_frame(scene, i, len(scenes), progress, palette)
            frame.save(os.path.join(frame_dir, f"f_{f:04d}.png"))

        scene_video = os.path.join(work_dir, f"scene_{i}.mp4")
        subprocess.run([
            "ffmpeg", "-y", "-framerate", str(FPS),
            "-i", os.path.join(frame_dir, "f_%04d.png"),
            "-i", audio_path,
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-shortest", scene_video,
        ], check=True, capture_output=True)
        scene_videos.append(scene_video)
        shutil.rmtree(frame_dir)

    concat_list = os.path.join(work_dir, "concat.txt")
    with open(concat_list, "w") as fh:
        for v in scene_videos:
            fh.write(f"file '{os.path.abspath(v)}'\n")

    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", concat_list, "-c", "copy", output_path,
    ], check=True, capture_output=True)

    return output_path, not narration_failed
