"""
Sahnalar ro'yxatidan animatsion .mp4 video yaratadi:
1. Har bir sahna uchun edge-tts bilan o'zbekcha ovoz generatsiya qilinadi.
2. Ovoz uzunligiga qarab, Pillow bilan so'z-so'z ochiluvchi kadrlar chiziladi.
3. ffmpeg har bir sahnani video+ovozga aylantiradi, so'ng hammasini birlashtiradi.
"""

import asyncio
import os
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

    # emoji / icon placeholder (colored circle with scene number, since
    # color-emoji glyphs are not reliably renderable via Pillow/DejaVu)
    cx, cy, r = W // 2, int(H * 0.34), 70
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=palette["accent"])
    num_text = str(index + 1)
    bbox = draw.textbbox((0, 0), num_text, font=font_emoji)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text((cx - tw / 2, cy - th / 2 - bbox[1]), num_text, font=font_emoji, fill=(20, 20, 30))

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

    for i, scene in enumerate(scenes):
        palette = PALETTE[i % len(PALETTE)]
        audio_path = os.path.join(work_dir, f"scene_{i}.mp3")
        asyncio.run(_synthesize(scene.get("text", ""), audio_path, voice))
        duration = max(_audio_duration(audio_path) + 0.6, 3.0)

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

    return output_path
