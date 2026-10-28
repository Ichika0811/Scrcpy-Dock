"""Generate the Scrcpy Dock application icon.

Design: a dark CMD-style terminal window with a dark Android robot head inside.
Rendered at high resolution and downsampled to a multi-size Windows .ico.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
SCALE = 4
SIZE = 256
CANVAS = SIZE * SCALE


def _font(size: int) -> ImageFont.FreeTypeFont:
    for name in ("consola.ttf", "CascadiaMono.ttf", "lucon.ttf"):
        path = Path("C:/Windows/Fonts") / name
        if path.is_file():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def _vertical_gradient(size: tuple[int, int], top: str, bottom: str) -> Image.Image:
    width, height = size
    top_rgb = tuple(int(top[i : i + 2], 16) for i in (1, 3, 5))
    bottom_rgb = tuple(int(bottom[i : i + 2], 16) for i in (1, 3, 5))
    image = Image.new("RGBA", size)
    pixels = image.load()
    for y in range(height):
        ratio = y / max(1, height - 1)
        color = tuple(
            round(top_rgb[index] * (1 - ratio) + bottom_rgb[index] * ratio)
            for index in range(3)
        )
        for x in range(width):
            pixels[x, y] = (*color, 255)
    return image


def build() -> Image.Image:
    s = SCALE
    canvas = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))

    # Soft drop shadow around the app tile.
    shadow = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle(
        (14 * s, 22 * s, (SIZE - 10) * s, (SIZE - 6) * s),
        radius=52 * s,
        fill=(0, 0, 0, 190),
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(13 * s))
    canvas.alpha_composite(shadow)

    # Outer app tile: nearly black with a graphite edge.
    tile = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
    tile_draw = ImageDraw.Draw(tile)
    tile_draw.rounded_rectangle(
        (8 * s, 8 * s, (SIZE - 8) * s, (SIZE - 8) * s),
        radius=50 * s,
        fill=(6, 8, 11, 255),
        outline=(30, 36, 42, 255),
        width=2 * s,
    )
    gradient = _vertical_gradient(
        ((SIZE - 16) * s, (SIZE - 16) * s), "#0d1115", "#040608"
    )
    mask = Image.new("L", ((SIZE - 16) * s, (SIZE - 16) * s), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (0, 0, (SIZE - 17) * s, (SIZE - 17) * s),
        radius=47 * s,
        fill=255,
    )
    tile.paste(gradient, (8 * s, 8 * s), mask)
    tile_draw.rounded_rectangle(
        (8 * s, 8 * s, (SIZE - 8) * s, (SIZE - 8) * s),
        radius=50 * s,
        outline=(44, 53, 62, 255),
        width=1 * s,
    )
    canvas.alpha_composite(tile)

    # Terminal window frame.
    terminal = (32 * s, 42 * s, (SIZE - 32) * s, (SIZE - 34) * s)
    term_shadow = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
    ImageDraw.Draw(term_shadow).rounded_rectangle(
        (36 * s, 48 * s, (SIZE - 28) * s, (SIZE - 28) * s),
        radius=20 * s,
        fill=(0, 0, 0, 210),
    )
    term_shadow = term_shadow.filter(ImageFilter.GaussianBlur(8 * s))
    canvas.alpha_composite(term_shadow)

    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle(
        terminal,
        radius=19 * s,
        fill=(11, 15, 19, 255),
        outline=(43, 53, 62, 255),
        width=2 * s,
    )

    # Minimal terminal chrome: a thin top strip, no window buttons or labels.
    title_bottom = 58 * s
    title = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
    title_draw = ImageDraw.Draw(title)
    title_draw.rounded_rectangle(
        (34 * s, 44 * s, (SIZE - 34) * s, title_bottom),
        radius=17 * s,
        fill=(17, 23, 29, 255),
    )
    title_draw.rectangle(
        (34 * s, title_bottom - 10 * s, (SIZE - 34) * s, title_bottom),
        fill=(17, 23, 29, 255),
    )
    canvas.alpha_composite(title)
    draw = ImageDraw.Draw(canvas)
    draw.line(
        (52 * s, title_bottom, (SIZE - 52) * s, title_bottom),
        fill=(36, 46, 55, 255),
        width=1 * s,
    )

    # Screen background, dark enough to keep the entire icon black.
    screen = (42 * s, 66 * s, (SIZE - 42) * s, (SIZE - 44) * s)
    screen_gradient = _vertical_gradient(
        ((screen[2] - screen[0]), (screen[3] - screen[1])), "#0a1110", "#050909"
    )
    screen_mask = Image.new("L", screen_gradient.size, 0)
    ImageDraw.Draw(screen_mask).rounded_rectangle(
        (0, 0, screen_gradient.width - 1, screen_gradient.height - 1),
        radius=11 * s,
        fill=255,
    )
    canvas.paste(screen_gradient, (screen[0], screen[1]), screen_mask)
    draw = ImageDraw.Draw(canvas)

    # Faint terminal prompt line at the bottom of the screen.
    prompt_font = _font(19 * s)
    draw.text(
        (52 * s, (SIZE - 52) * s),
        ">_",
        font=prompt_font,
        fill=(52, 74, 64, 255),
        anchor="ls",
    )

    # Soft halo behind the robot head.
    halo = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
    ImageDraw.Draw(halo).ellipse(
        (58 * s, 78 * s, (SIZE - 58) * s, (SIZE - 74) * s),
        fill=(22, 41, 32, 135),
    )
    halo = halo.filter(ImageFilter.GaussianBlur(16 * s))
    canvas.alpha_composite(halo)

    draw = ImageDraw.Draw(canvas)
    head_fill = (63, 91, 74, 255)
    eye_fill = (194, 216, 201, 255)

    # Antennae attach to the upper sides of the dome and point out at 45°.
    for start, end in (
        ((94, 116), (72, 86)),
        ((162, 116), (184, 86)),
    ):
        draw.line(
            (start[0] * s, start[1] * s, end[0] * s, end[1] * s),
            fill=head_fill,
            width=9 * s,
        )
        draw.ellipse(
            (
                (end[0] - 5.5) * s,
                (end[1] - 5.5) * s,
                (end[0] + 5.5) * s,
                (end[1] + 5.5) * s,
            ),
            fill=head_fill,
        )

    # Classic Android head silhouette: wide dome, flat base, no outline.
    dome = (64 * s, 94 * s, 192 * s, 174 * s)
    draw.pieslice(dome, start=180, end=360, fill=head_fill)
    draw.rectangle((64 * s, 134 * s, 192 * s, 174 * s), fill=head_fill)

    # The original Android mascot has light eyes, not dark cut-outs.
    for cx in (102, 154):
        draw.ellipse(
            ((cx - 8) * s, 127 * s, (cx + 8) * s, 143 * s),
            fill=eye_fill,
        )

    # Thin reflection edge on the terminal frame.
    draw.line(
        (52 * s, 44 * s, (SIZE - 52) * s, 44 * s),
        fill=(52, 63, 73, 255),
        width=1 * s,
    )

    return canvas.resize((SIZE, SIZE), Image.Resampling.LANCZOS)


def main() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    icon = build()
    icon.save(ASSETS / "icon.png")
    icon.save(
        ASSETS / "icon.ico",
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )
    print(f"wrote {ASSETS / 'icon.ico'} and icon.png")


if __name__ == "__main__":
    main()
