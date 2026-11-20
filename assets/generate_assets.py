#!/usr/bin/env python3
"""
GTA VI OS (Vice OS) Asset Generator
Generates original neon Miami-inspired wallpapers and icons procedurally.
Optimized for fast generation, low memory footprint, and high aesthetic quality.
"""

import os
import sys
import math
import argparse
from PIL import Image, ImageDraw, ImageFilter


def create_wallpaper(output_dir: str = "/usr/share/backgrounds") -> None:
    """Generate a 1080p neon grid wallpaper natively."""
    width, height = 1920, 1080
    img = Image.new('RGB', (width, height))
    draw = ImageDraw.Draw(img)

    # Optimized Gradient Sky (Deep purple to magenta)
    sky_gradient = Image.new('RGB', (1, height // 2))
    sky_pixels = sky_gradient.load()
    for y in range(height // 2):
        r = int(255 * (y / (height / 2)))
        g = int(20 * (y / (height / 2)))
        b = int(150 * (y / (height / 2)))
        sky_pixels[0, y] = (r, g, b)

    sky_gradient = sky_gradient.resize((width, height // 2))
    img.paste(sky_gradient, (0, 0))

    # Fill bottom half with black for the road
    draw.rectangle(
        [(0, height // 2), (width, height)], fill=(5, 5, 5)
    )

    # Neon Sun (Perfect Cyan to Magenta gradient)
    sun_cx, sun_cy = width // 2, height // 2 - 150
    sun_r = 250
    for i in range(sun_r, 0, -1):
        blend = i / sun_r
        r = int(255 * (1 - blend) + 0 * blend)
        g = int(0 * (1 - blend) + 255 * blend)
        b = int(255 * (1 - blend) + 255 * blend)
        draw.ellipse(
            (sun_cx - i, sun_cy - i, sun_cx + i, sun_cy + i),
            fill=(r, g, b)
        )

    # Cut horizontal lines out of the sun for retro effect
    # Dynamically calculate lines based on sun radius
    num_lines = 6
    spacing = sun_r // (num_lines + 2)
    for i in range(1, num_lines + 1):
        y_offset = sun_cy + (i * spacing)
        dy = y_offset - sun_cy
        if dy < sun_r:
            dx = int(math.sqrt(sun_r**2 - dy**2))
            draw.rectangle(
                [(sun_cx - dx, y_offset), (sun_cx + dx, y_offset + 8)],
                fill=(5, 5, 5)
            )

    # Add a subtle horizon glow
    glow = Image.new('RGBA', (width, 160), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    glow_draw.rectangle([(0, 60), (width, 100)], fill=(255, 0, 255, 180))
    glow = glow.filter(ImageFilter.GaussianBlur(radius=25))
    img.paste(glow, (0, height // 2 - 80), glow)

    # Grid Floor (Cyan) - Perspective lines
    draw.line(
        [(0, height // 2), (width // 2, height)],
        fill=(0, 255, 255), width=4
    )
    draw.line(
        [(width, height // 2), (width // 2, height)],
        fill=(0, 255, 255), width=4
    )

    for i in range(1, 20):
        x_offset = (width // 2) * (i / 20)
        draw.line(
            [(width // 2 - x_offset, height // 2), (0, height)],
            fill=(0, 255, 255), width=2
        )
        draw.line(
            [(width // 2 + x_offset, height // 2), (width, height)],
            fill=(0, 255, 255), width=2
        )

    # Grid Floor - Horizontal lines
    for i in range(1, 15):
        y = height // 2 + (height // 2) * (i / 15)**2
        draw.line([(0, y), (width, y)], fill=(0, 255, 255), width=2)

    try:
        os.makedirs(output_dir, exist_ok=True)
        img.save(
            os.path.join(output_dir, 'vice_neon.jpg'),
            'JPEG', quality=90
        )
        print("[*] Wallpaper generated successfully.")
    except OSError as e:
        print(f"[!] Failed to save wallpaper: {e}", file=sys.stderr)
        raise


def create_icon(output_dir: str = "/usr/share/pixmaps") -> None:
    """Generate a 512x512 neon 'V' dock icon using 4x supersampling."""
    # Use 4x supersampling for anti-aliased, crisp edges
    scale = 4
    size = 512 * scale
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Draw a dark rounded rectangle background
    draw.rounded_rectangle(
        [50 * scale, 50 * scale, 462 * scale, 462 * scale],
        radius=80 * scale,
        fill=(18, 0, 36, 220),  # Semi-transparent dark purple
        outline=(0, 255, 255),
        width=12 * scale
    )

    # Draw a Neon 'V' using filled polygons for crisp joints
    # Outer polygon (Magenta)
    s = scale
    outer_v = [
        (120 * s, 140 * s), (260 * s, 390 * s), (400 * s, 140 * s),
        (340 * s, 140 * s), (260 * s, 270 * s), (180 * s, 140 * s)
    ]
    draw.polygon(outer_v, fill=(255, 0, 255, 255))

    # Inner polygon (Cyan) to create the neon stroke effect
    inner_v = [
        (140 * s, 140 * s), (260 * s, 350 * s), (380 * s, 140 * s),
        (350 * s, 140 * s), (260 * s, 290 * s), (170 * s, 140 * s)
    ]
    draw.polygon(inner_v, fill=(0, 255, 255, 255))

    # Downsample to 512x512 using high-quality LANCZOS filter
    img = img.resize((512, 512), Image.LANCZOS)

    try:
        os.makedirs(output_dir, exist_ok=True)
        img.save(os.path.join(output_dir, 'vice-app.png'), 'PNG')
        print("[*] Icon generated successfully.")
    except OSError as e:
        print(f"[!] Failed to save icon: {e}", file=sys.stderr)
        raise


def main() -> None:
    parser = argparse.ArgumentParser(
        description="GTA VI OS Asset Generator"
    )
    parser.add_argument(
        "--wallpaper-dir", type=str,
        default="/usr/share/backgrounds",
        help="Output directory for wallpaper"
    )
    parser.add_argument(
        "--icon-dir", type=str,
        default="/usr/share/pixmaps",
        help="Output directory for icon"
    )
    args = parser.parse_args()

    create_wallpaper(args.wallpaper_dir)
    create_icon(args.icon_dir)


if __name__ == "__main__":
    main()