#!/usr/bin/env python3
"""Create a lightweight README demo GIF from the sample pet spritesheet."""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw


CELL_WIDTH = 192
CELL_HEIGHT = 208
CANVAS_SIZE = (520, 300)
PET_HEIGHT = 122
FRAME_MS = 80
IDLE_ROW = 0
RUN_ROW = 7


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: make_demo_gif.py <spritesheet.webp> <output.gif>", file=sys.stderr)
        return 2

    spritesheet = Path(sys.argv[1])
    output = Path(sys.argv[2])

    sheet = Image.open(spritesheet).convert("RGBA")
    idle = [crop_frame(sheet, IDLE_ROW, index) for index in range(6)]
    running = [crop_frame(sheet, RUN_ROW, index) for index in range(6)]

    frames: list[Image.Image] = []
    durations: list[int] = []

    add_idle_frame(frames, durations, idle[0], blink=False, duration=850)
    add_idle_frame(frames, durations, idle[0], blink=True, duration=360)
    add_idle_frame(frames, durations, idle[0], blink=False, duration=520)
    add_idle_frame(frames, durations, idle[0], blink=True, duration=280)
    add_idle_frame(frames, durations, idle[0], blink=False, duration=360)

    for index in range(48):
        progress = index / 47
        x = int(28 + progress * 360)
        frame = draw_background()
        draw_pet(frame, running[index % len(running)], x=x, y=126)
        frames.append(frame)
        durations.append(FRAME_MS)

    output.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(
        output,
        save_all=True,
        append_images=frames[1:],
        duration=durations,
        loop=0,
        optimize=True,
    )
    print(f"wrote {display_path(output)}")
    return 0


def crop_frame(sheet: Image.Image, row: int, column: int) -> Image.Image:
    left = column * CELL_WIDTH
    top = row * CELL_HEIGHT
    cell = sheet.crop((left, top, left + CELL_WIDTH, top + CELL_HEIGHT))
    bbox = cell.getchannel("A").getbbox()
    return cell.crop(bbox) if bbox else cell


def add_idle_frame(frames: list[Image.Image], durations: list[int], pet: Image.Image, blink: bool, duration: int) -> None:
    frame = draw_background()
    draw_pet(frame, pet, x=34, y=126, blink=blink)
    frames.append(frame)
    durations.append(duration)


def draw_background() -> Image.Image:
    image = Image.new("RGB", CANVAS_SIZE, "#eef1f4")
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 236, CANVAS_SIZE[0], CANVAS_SIZE[1]), fill="#d7dce1")
    draw.rectangle((0, 235, CANVAS_SIZE[0], 235), fill="#c2c9d0")
    return image


def draw_pet(frame: Image.Image, pet: Image.Image, x: int, y: int, blink: bool = False) -> None:
    scale = PET_HEIGHT / pet.height
    pet_size = (max(1, int(pet.width * scale)), PET_HEIGHT)
    pet = pet.resize(pet_size, Image.Resampling.NEAREST)
    if blink:
        pet = closed_eye_frame(pet)
    frame.paste(pet, (x, y), pet)


def closed_eye_frame(pet: Image.Image) -> Image.Image:
    pet = pet.copy()
    eye_pixels = []
    for y in range(pet.height):
        for x in range(pet.width):
            red, green, blue, alpha = pet.getpixel((x, y))
            if alpha > 100 and red > 150 and green > 70 and blue < 90:
                eye_pixels.append((x, y))

    if len(eye_pixels) < 10:
        return pet

    center_x = (min(x for x, _y in eye_pixels) + max(x for x, _y in eye_pixels)) / 2
    clusters = [
        [(x, y) for x, y in eye_pixels if x < center_x],
        [(x, y) for x, y in eye_pixels if x >= center_x],
    ]

    draw = ImageDraw.Draw(pet)
    fur = (126, 112, 108, 255)
    outline = (28, 29, 30, 255)
    for cluster in clusters:
        if not cluster:
            continue
        left = max(0, min(x for x, _y in cluster) - 3)
        top = max(0, min(y for _x, y in cluster) - 2)
        right = min(pet.width - 1, max(x for x, _y in cluster) + 3)
        bottom = min(pet.height - 1, max(y for _x, y in cluster) + 2)
        mid_y = (top + bottom) // 2
        draw.rounded_rectangle((left, top, right, bottom), radius=2, fill=fur)
        draw.line((left + 1, mid_y, right - 1, mid_y), fill=outline, width=2)

    return pet


def display_path(path: Path) -> str:
    try:
        return str(path.relative_to(Path.cwd()))
    except ValueError:
        return str(path)


if __name__ == "__main__":
    raise SystemExit(main())
