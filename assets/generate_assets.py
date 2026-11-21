#!/usr/bin/env python3
"""
GTA VI OS (Vice OS) Asset Generator
Generates authentic Leonida/Vice City sunset wallpapers and a custom GTA VI x Debian
swirl emblem procedurally using Pillow.
"""

import os
import sys
import math
import argparse
from PIL import Image, ImageDraw, ImageFilter


def _lerp_color(c1: tuple, c2: tuple, t: float) -> tuple:
    t = max(0.0, min(1.0, t))
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(len(c1)))


def _vertical_gradient(width: int, height: int, stops: list) -> Image.Image:
    """Build a vertical RGBA/RGB gradient image across normalized stops [(pos, (r,g,b)), ...]."""
    mode = "RGBA" if len(stops[0][1]) == 4 else "RGB"
    strip = Image.new(mode, (1, height))
    pixels = strip.load()
    for y in range(height):
        pos = y / max(1, height - 1)
        color = stops[-1][1]
        for idx in range(len(stops) - 1):
            p0, c0 = stops[idx]
            p1, c1 = stops[idx + 1]
            if p0 <= pos <= p1:
                local_t = (pos - p0) / max(1e-6, p1 - p0)
                color = _lerp_color(c0, c1, local_t)
                break
        pixels[0, y] = color
    return strip.resize((width, height), Image.BILINEAR)


def _draw_palm_tree(draw: ImageDraw.ImageDraw, base_x: float, base_y: float,
                    top_x: float, top_y: float, scale: float, color: tuple) -> None:
    """Draw a silhouetted coastal coconut palm tree with curved trunk and arched fronds."""
    # Curved trunk polygon
    steps = 18
    left_pts = []
    right_pts = []
    for i in range(steps + 1):
        t = i / steps
        # Quadratic bezier control point bows inward smoothly
        ctrl_x = (base_x + top_x) / 2.0 + (top_x - base_x) * 0.22
        ctrl_y = (base_y + top_y) / 2.0
        bx = (1 - t) ** 2 * base_x + 2 * (1 - t) * t * ctrl_x + t ** 2 * top_x
        by = (1 - t) ** 2 * base_y + 2 * (1 - t) * t * ctrl_y + t ** 2 * top_y
        half_w = (15.0 * (1.0 - 0.65 * t)) * scale
        left_pts.append((bx - half_w, by))
        right_pts.append((bx + half_w, by))
    draw.polygon(left_pts + list(reversed(right_pts)), fill=color)

    # Fronds radiating from crown (top_x, top_y)
    frond_angles = [-165, -135, -100, -58, -22, 14, 42, 160]
    for idx, deg in enumerate(frond_angles):
        ang = math.radians(deg)
        length = (165 if idx % 2 == 0 else 138) * scale
        droop = (52 if abs(deg) > 110 else 44) * scale
        end_x = top_x + math.cos(ang) * length
        end_y = top_y + math.sin(ang) * length + droop
        mid_x = top_x + math.cos(ang) * (length * 0.52)
        mid_y = top_y + math.sin(ang) * (length * 0.45)

        # Spine
        draw.line([(top_x, top_y), (mid_x, mid_y), (end_x, end_y)], fill=color, width=max(2, int(4 * scale)))
        # Leaflets hanging along the frond
        for f in range(3, 18):
            ft = f / 18.0
            lx = (1 - ft) ** 2 * top_x + 2 * (1 - ft) * ft * mid_x + ft ** 2 * end_x
            ly = (1 - ft) ** 2 * top_y + 2 * (1 - ft) * ft * mid_y + ft ** 2 * end_y
            leaf_len = math.sin(ft * math.pi) * 42.0 * scale
            dx_dir = 1.0 if end_x >= top_x else -1.0
            draw.polygon([
                (lx, ly),
                (lx + dx_dir * leaf_len * 0.35, ly + leaf_len * 0.72),
                (lx + dx_dir * leaf_len * 0.08, ly + leaf_len),
                (lx - dx_dir * leaf_len * 0.12, ly + 4 * scale),
            ], fill=color)


def create_gta6_debian_logo(size: int = 512, with_badge: bool = True) -> Image.Image:
    """
    Generate the custom GTA VI x Debian Swirl emblem on a transparent canvas.
    Combines the Debian spiral swirl in a Vice City sunset gradient with a bold 'VI' badge.
    """
    scale = 4
    s = size * scale

    badge = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    sunset_grad = _vertical_gradient(s, s, [
        (0.0, (255, 194, 120, 255)),
        (0.32, (255, 107, 139, 255)),
        (0.65, (255, 46, 151, 255)),
        (1.0, (140, 59, 255, 255)),
    ])
    if with_badge:
        badge_draw = ImageDraw.Draw(badge)
        pad = int(s * 0.04)
        badge_draw.ellipse([pad, pad, s - pad, s - pad], fill=(18, 12, 34, 238))

        ring_mask = Image.new("L", (s, s), 0)
        ring_draw = ImageDraw.Draw(ring_mask)
        ring_w = max(4, int(s * 0.022))
        ring_draw.ellipse([pad, pad, s - pad, s - pad], outline=230, width=ring_w)
        badge.paste(sunset_grad, (0, 0), ring_mask)

    # Debian open spiral swirl mask (dense steps so tapered tail is razor-smooth)
    swirl_mask = Image.new("L", (s, s), 0)
    swirl_draw = ImageDraw.Draw(swirl_mask)
    cx, cy = s * 0.48, s * 0.47
    points = 960
    for i in range(points):
        t = i / (points - 1)
        # Tight center curl opening outward counter-clockwise, ending lower-left
        theta = 0.55 + t * (2.95 * math.pi)
        r = s * (0.015 + 0.315 * (t ** 1.05))
        px = cx + r * math.cos(theta)
        py = cy + r * math.sin(theta)
        if t < 0.72:
            half_w = s * (0.010 + 0.036 * math.sin((t / 0.72) * (math.pi * 0.65)))
        else:
            tail_t = (t - 0.72) / 0.28
            half_w = s * (0.041 * (1.0 - tail_t ** 0.85) + 0.004)
        swirl_draw.ellipse([px - half_w, py - half_w, px + half_w, py + half_w], fill=255)

    # Outer Vice neon glow behind swirl
    glow_layer = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    glow_fill = _vertical_gradient(s, s, [
        (0.0, (255, 138, 91, 170)),
        (0.5, (255, 46, 151, 190)),
        (1.0, (140, 59, 255, 170)),
    ])
    glow_layer.paste(glow_fill, (0, 0), swirl_mask)
    glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(radius=int(18 * scale)))
    badge = Image.alpha_composite(badge, glow_layer)

    # Crisp gradient-filled Debian swirl
    swirl_layer = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    swirl_layer.paste(sunset_grad, (0, 0), swirl_mask)
    badge = Image.alpha_composite(badge, swirl_layer)

    # Bold geometric 'VI' Roman numeral tucked cleanly at bottom-right
    vi_layer = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    vi_draw = ImageDraw.Draw(vi_layer)

    def _scaled(pts):
        return [(x * s, y * s) for (x, y) in pts]

    v_poly = _scaled([
        (0.54, 0.56), (0.615, 0.56), (0.665, 0.745),
        (0.715, 0.56), (0.79, 0.56), (0.70, 0.84), (0.63, 0.84),
    ])
    i_poly = _scaled([
        (0.815, 0.56), (0.885, 0.56), (0.885, 0.84), (0.815, 0.84),
    ])

    # Dark violet silhouette border + subtle pink-peach glow around VI
    stroke_w = max(4, int(s * 0.024))
    for poly in (v_poly, i_poly):
        vi_draw.polygon(poly, fill=(18, 12, 34, 255))
        for j in range(len(poly)):
            p1 = poly[j]
            p2 = poly[(j + 1) % len(poly)]
            vi_draw.line([p1, p2], fill=(18, 12, 34, 255), width=stroke_w)
            vi_draw.ellipse([p1[0] - stroke_w / 2, p1[1] - stroke_w / 2,
                             p1[0] + stroke_w / 2, p1[1] + stroke_w / 2], fill=(18, 12, 34, 255))

    vi_mask = Image.new("L", (s, s), 0)
    vi_mask_draw = ImageDraw.Draw(vi_mask)
    vi_mask_draw.polygon(v_poly, fill=255)
    vi_mask_draw.polygon(i_poly, fill=255)
    vi_fill = _vertical_gradient(s, s, [
        (0.54, (255, 255, 255, 255)),
        (0.72, (255, 224, 236, 255)),
        (0.86, (255, 165, 195, 255)),
    ])
    vi_layer.paste(vi_fill, (0, 0), vi_mask)
    badge = Image.alpha_composite(badge, vi_layer)

    return badge.resize((size, size), Image.LANCZOS)


def create_wallpaper(output_dir: str = "/usr/share/backgrounds") -> None:
    """Generate a 1080p GTA VI Vice City sunset + Debian emblem wallpaper."""
    width, height = 1920, 1080
    horizon_y = int(height * 0.64)

    # 1. Leonida twilight-to-sunset sky gradient
    sky = _vertical_gradient(width, horizon_y, [
        (0.0, (17, 10, 36)),
        (0.28, (54, 22, 92)),
        (0.58, (148, 36, 114)),
        (0.84, (235, 92, 130)),
        (1.0, (255, 158, 96)),
    ])
    img = Image.new("RGBA", (width, height), (14, 9, 28, 255))
    img.paste(sky, (0, 0))

    # 2. Tropical sunset sun + horizon haze
    sun_cx, sun_cy = width // 2, horizon_y - 36
    sun_r = 215
    sun_halo = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    halo_draw = ImageDraw.Draw(sun_halo)
    halo_draw.ellipse(
        [sun_cx - sun_r - 90, sun_cy - sun_r - 90, sun_cx + sun_r + 90, sun_cy + sun_r + 90],
        fill=(255, 90, 145, 95)
    )
    sun_halo = sun_halo.filter(ImageFilter.GaussianBlur(radius=55))
    img = Image.alpha_composite(img, sun_halo)

    sun_mask = Image.new("L", (width, height), 0)
    sun_draw = ImageDraw.Draw(sun_mask)
    sun_draw.ellipse([sun_cx - sun_r, sun_cy - sun_r, sun_cx + sun_r, sun_cy + sun_r], fill=255)
    # Retro horizon stripes through lower portion of the sun
    for s_idx, bar_h in enumerate((4, 6, 8, 10)):
        bar_y = sun_cy - 20 + s_idx * 24
        sun_draw.rectangle([sun_cx - sun_r - 10, bar_y, sun_cx + sun_r + 10, bar_y + bar_h], fill=0)
    # Clip sun at ocean horizon
    sun_draw.rectangle([0, horizon_y, width, height], fill=0)

    sun_grad = _vertical_gradient(width, height, [
        (0.35, (255, 226, 130, 255)),
        (0.52, (255, 118, 135, 255)),
        (0.65, (224, 42, 132, 255)),
    ])
    img.paste(sun_grad, (0, 0), sun_mask)

    # 3. Miami skyline silhouettes flanking center
    draw = ImageDraw.Draw(img)
    skyline_color = (26, 13, 46, 255)
    buildings = [
        (360, 74), (420, 118), (475, 86), (520, 148), (575, 102),
        (630, 132), (685, 76), (735, 95),
        (1140, 88), (1195, 138), (1255, 106), (1310, 162), (1375, 114),
        (1430, 90), (1490, 124), (1550, 78),
    ]
    for bx, bh in buildings:
        draw.rectangle([bx, horizon_y - bh, bx + 48, horizon_y], fill=skyline_color)
        # Subtle neon window glints
        for wy in range(horizon_y - bh + 12, horizon_y - 14, 18):
            if (bx + wy) % 3 == 0:
                draw.rectangle([bx + 10, wy, bx + 16, wy + 5], fill=(255, 95, 165, 145))
            if (bx + wy) % 5 == 0:
                draw.rectangle([bx + 28, wy, bx + 34, wy + 5], fill=(0, 229, 195, 135))

    # 4. Dark tropical ocean + sunset water shimmer
    ocean = _vertical_gradient(width, height - horizon_y, [
        (0.0, (44, 18, 72, 255)),
        (0.35, (22, 12, 42, 255)),
        (1.0, (11, 7, 22, 255)),
    ])
    img.paste(ocean, (0, horizon_y))
    draw = ImageDraw.Draw(img)
    draw.line([(0, horizon_y), (width, horizon_y)], fill=(255, 175, 115, 180), width=2)

    for i in range(1, 22):
        ry = horizon_y + int((i ** 1.35) * 6.8)
        if ry >= height - 48:
            break
        half_span = max(32, int(230 * (1.0 - i / 25.0) + (i % 3) * 28))
        alpha = max(35, 185 - i * 7)
        col = (255, 140, 115, alpha) if i % 2 == 0 else (255, 62, 148, alpha)
        draw.line([(sun_cx - half_span, ry), (sun_cx + half_span, ry)], fill=col, width=max(2, 5 - i // 5))

    # 5. Coastal palm silhouettes on edges (leaves top-left clear for desktop icons)
    palm_color = (13, 8, 24, 255)
    _draw_palm_tree(draw, 140, height, 235, int(height * 0.42), 1.35, palm_color)
    _draw_palm_tree(draw, width - 90, height, width - 210, int(height * 0.34), 1.55, palm_color)
    _draw_palm_tree(draw, width - 260, height, width - 335, int(height * 0.51), 1.05, palm_color)

    # 6. Centered subtle GTA VI x Debian Swirl watermark (badge-less swirl floating cleanly in sky)
    emblem = create_gta6_debian_logo(320, with_badge=False)
    r_ch, g_ch, b_ch, a_ch = emblem.split()
    a_ch = a_ch.point(lambda px: int(px * 0.88))
    emblem = Image.merge("RGBA", (r_ch, g_ch, b_ch, a_ch))
    emb_x = (width - emblem.width) // 2
    emb_y = int(height * 0.25) - emblem.height // 2
    img = Image.alpha_composite(img, _paste_rgba(width, height, emblem, emb_x, emb_y))

    # 7. Seamless left + bottom vignette so Desktop icons and bottom taskbar text stay ultra readable
    vig_canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    left_mask = Image.new("L", (420, 1))
    lm_pix = left_mask.load()
    for x in range(420):
        lm_pix[x, 0] = int(105 * (1.0 - x / 419.0) ** 1.8)
    left_mask = left_mask.resize((420, height), Image.BILINEAR)
    vig_fill = Image.new("RGBA", (420, height), (12, 8, 24, 255))
    vig_canvas.paste(vig_fill, (0, 0), left_mask)
    img = Image.alpha_composite(img, vig_canvas)

    try:
        os.makedirs(output_dir, exist_ok=True)
        img.convert("RGB").save(
            os.path.join(output_dir, "vice_neon.jpg"),
            "JPEG", quality=92
        )
        print("[*] Wallpaper generated successfully.")
    except OSError as e:
        print(f"[!] Failed to save wallpaper: {e}", file=sys.stderr)
        raise


def _paste_rgba(canvas_w: int, canvas_h: int, overlay: Image.Image, x: int, y: int) -> Image.Image:
    layer = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
    layer.paste(overlay, (x, y), overlay)
    return layer


def create_icon(output_dir: str = "/usr/share/pixmaps") -> None:
    """Generate the GTA VI x Debian Swirl logos in /usr/share/pixmaps."""
    logo = create_gta6_debian_logo(512)
    try:
        os.makedirs(output_dir, exist_ok=True)
        logo.save(os.path.join(output_dir, "vice-debian-gta6.png"), "PNG")
        logo.save(os.path.join(output_dir, "vice-app.png"), "PNG")
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
