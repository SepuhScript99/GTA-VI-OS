#!/usr/bin/env python3
"""
GTA VI OS (Vice OS) Asset Generator.
Generates an authentic, atmospheric Leonida coastal dusk wallpaper and a clean
modern GTA VI x Debian swirl emblem using Pillow (zero cheesy retro grid clutter).
"""

import argparse
import math
import os
import random
import sys
from PIL import Image, ImageChops, ImageDraw, ImageFilter


def _lerp_color(c1: tuple, c2: tuple, t: float) -> tuple:
    t = max(0.0, min(1.0, t))
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(len(c1)))


def _vertical_gradient(width: int, height: int, stops: list) -> Image.Image:
    """Build a smooth vertical RGBA/RGB gradient image from normalized color stops."""
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
                local_t = local_t * local_t * (3.0 - 2.0 * local_t)
                color = _lerp_color(c0, c1, local_t)
                break
        pixels[0, y] = color
    return strip.resize((width, height), Image.BILINEAR)


def _horizontal_gradient(width: int, height: int, stops: list) -> Image.Image:
    """Build a smooth horizontal RGBA/RGB gradient image from normalized color stops."""
    mode = "RGBA" if len(stops[0][1]) == 4 else "RGB"
    strip = Image.new(mode, (width, 1))
    pixels = strip.load()
    for x in range(width):
        pos = x / max(1, width - 1)
        color = stops[-1][1]
        for idx in range(len(stops) - 1):
            p0, c0 = stops[idx]
            p1, c1 = stops[idx + 1]
            if p0 <= pos <= p1:
                local_t = (pos - p0) / max(1e-6, p1 - p0)
                local_t = local_t * local_t * (3.0 - 2.0 * local_t)
                color = _lerp_color(c0, c1, local_t)
                break
        pixels[x, 0] = color
    return strip.resize((width, height), Image.BILINEAR)


def _draw_palm_tree(
    draw: ImageDraw.ImageDraw,
    base_x: float,
    base_y: float,
    top_x: float,
    top_y: float,
    scale: float,
    color: tuple,
) -> None:
    """Draw a fluid, natural coastal coconut palm silhouette with sweeping curved fronds."""
    steps = 26
    left_pts = []
    right_pts = []
    ctrl_x = (base_x + top_x) / 2.0 + (top_x - base_x) * 0.28
    ctrl_y = (base_y + top_y) / 2.0 + 35 * scale
    for i in range(steps + 1):
        t = i / steps
        bx = (1 - t) ** 2 * base_x + 2 * (1 - t) * t * ctrl_x + t ** 2 * top_x
        by = (1 - t) ** 2 * base_y + 2 * (1 - t) * t * ctrl_y + t ** 2 * top_y
        half_w = (12.5 * (1.0 - 0.66 * t)) * scale
        left_pts.append((bx - half_w, by))
        right_pts.append((bx + half_w, by))
    draw.polygon(left_pts + list(reversed(right_pts)), fill=color)

    # Crown frond arcs: (start_angle_deg, droop_px, length_px)
    fronds = [
        (-172, 92, 182),
        (-146, 86, 174),
        (-116, 70, 152),
        (-82, 54, 134),
        (-44, 62, 160),
        (-12, 82, 176),
        (16, 98, 165),
        (158, 95, 146),
    ]
    for deg, droop, base_len in fronds:
        ang = math.radians(deg)
        length = base_len * scale
        d_px = droop * scale
        end_x = top_x + math.cos(ang) * length
        end_y = top_y + math.sin(ang) * length + d_px
        mid_x = top_x + math.cos(ang) * (length * 0.50)
        mid_y = top_y + math.sin(ang) * (length * 0.42) + d_px * 0.14

        spine_pts = []
        for k in range(25):
            st = k / 24.0
            sx = (1 - st) ** 2 * top_x + 2 * (1 - st) * st * mid_x + st ** 2 * end_x
            sy = (1 - st) ** 2 * top_y + 2 * (1 - st) * st * mid_y + st ** 2 * end_y
            spine_pts.append((sx, sy))
        draw.line(spine_pts, fill=color, width=max(2, int(3.2 * scale)))

        # Swept, tapering palm leaflets curving downward along the frond direction
        dir_x = 1.0 if end_x >= top_x else -1.0
        for f in range(3, 23):
            ft = f / 24.0
            lx = (1 - ft) ** 2 * top_x + 2 * (1 - ft) * ft * mid_x + ft ** 2 * end_x
            ly = (1 - ft) ** 2 * top_y + 2 * (1 - ft) * ft * mid_y + ft ** 2 * end_y
            l_len = (math.sin(ft * math.pi) ** 0.78) * 38.0 * scale
            tip_x = lx + dir_x * l_len * 0.52
            tip_y = ly + l_len * 0.92
            ctrl_lx = lx + dir_x * l_len * 0.36
            ctrl_ly = ly + l_len * 0.34
            w_base = max(1.5, 3.0 * scale * (1.0 - 0.55 * ft))
            draw.polygon([
                (lx - dir_x * w_base * 0.3, ly),
                (ctrl_lx + dir_x * w_base, ctrl_ly),
                (tip_x, tip_y),
                (ctrl_lx - dir_x * w_base * 0.4, ctrl_ly + 2.0 * scale),
            ], fill=color)


def create_gta6_debian_logo(size: int = 512, with_badge: bool = True) -> Image.Image:
    """
    Generate the refined GTA VI x Debian Swirl emblem on a transparent canvas.
    Combines a satin slate squircle-badge, coral-to-gold Debian swirl, and crisp 'VI' mark.
    """
    scale = 4
    s = size * scale

    badge = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    sunset_grad = _vertical_gradient(s, s, [
        (0.0, (247, 200, 115, 255)),   # #F7C873 warm gold
        (0.45, (255, 154, 98, 255)),   # #FF9A62 sunset peach
        (1.0, (255, 94, 126, 255)),    # #FF5E7E coral-pink
    ])

    if with_badge:
        pad = int(s * 0.06)
        rad = int(s * 0.24)
        mask = Image.new("L", (s, s), 0)
        ImageDraw.Draw(mask).rounded_rectangle(
            [pad, pad, s - pad, s - pad], radius=rad, fill=255
        )
        satin_fill = _vertical_gradient(s, s, [
            (0.0, (28, 32, 50, 248)),   # #1C2032 satin top
            (0.5, (21, 24, 38, 248)),   # #151826 core slate
            (1.0, (14, 16, 26, 248)),   # #0E101A deep base
        ])
        badge.paste(satin_fill, (0, 0), mask)

        # Clean structural hairline border
        ring_w = max(4, int(s * 0.016))
        rim_base = Image.new("RGBA", (s, s), (0, 0, 0, 0))
        ImageDraw.Draw(rim_base).rounded_rectangle(
            [pad, pad, s - pad, s - pad],
            radius=rad,
            outline=(48, 54, 78, 225),
            width=ring_w,
        )
        badge = Image.alpha_composite(badge, rim_base)

        # Crisp coral-peach-gold top rim sheen (pure sunset color without muddy blending)
        top_sheen_mask = Image.new("L", (s, s), 0)
        ImageDraw.Draw(top_sheen_mask).rounded_rectangle(
            [pad, pad, s - pad, s - pad], radius=rad, outline=255, width=ring_w
        )
        fade = _vertical_gradient(s, s, [
            (0.0, (235, 235, 235, 235)),
            (0.32, (90, 90, 90, 90)),
            (0.65, (0, 0, 0, 0)),
            (1.0, (0, 0, 0, 0)),
        ]).convert("L")
        top_sheen_mask = ImageChops.multiply(top_sheen_mask, fade)
        rim_grad = _horizontal_gradient(s, s, [
            (0.0, (255, 94, 126, 255)),
            (0.5, (255, 154, 98, 255)),
            (1.0, (247, 200, 115, 255)),
        ])
        sheen_layer = Image.new("RGBA", (s, s), (0, 0, 0, 0))
        sheen_layer.paste(rim_grad, (0, 0), top_sheen_mask)
        badge = Image.alpha_composite(badge, sheen_layer)

    # Debian open spiral swirl mask centered cleanly
    swirl_mask = Image.new("L", (s, s), 0)
    swirl_draw = ImageDraw.Draw(swirl_mask)
    cx, cy = s * 0.455, s * 0.455
    points = 960
    for i in range(points):
        t = i / (points - 1)
        theta = 0.55 + t * (2.92 * math.pi)
        r = s * (0.014 + 0.285 * (t ** 1.05))
        px = cx + r * math.cos(theta)
        py = cy + r * math.sin(theta)
        if t < 0.72:
            half_w = s * (0.011 + 0.035 * math.sin((t / 0.72) * (math.pi * 0.65)))
        else:
            tail_t = (t - 0.72) / 0.28
            half_w = s * (0.040 * (1.0 - tail_t ** 0.85) + 0.004)
        swirl_draw.ellipse(
            [px - half_w, py - half_w, px + half_w, py + half_w], fill=255
        )

    swirl_layer = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    swirl_layer.paste(sunset_grad, (0, 0), swirl_mask)
    badge = Image.alpha_composite(badge, swirl_layer)

    # Editorial geometric 'VI' Roman numeral tucked cleanly at bottom-right
    vi_layer = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    vi_draw = ImageDraw.Draw(vi_layer)

    def _scaled(pts):
        return [(x * s, y * s) for (x, y) in pts]

    v_poly = _scaled([
        (0.52, 0.55), (0.59, 0.55), (0.64, 0.72),
        (0.69, 0.55), (0.76, 0.55), (0.675, 0.81), (0.605, 0.81),
    ])
    i_poly = _scaled([
        (0.785, 0.55), (0.85, 0.55), (0.85, 0.81), (0.785, 0.81),
    ])

    halo_w = max(4, int(s * 0.026))
    halo_col = (18, 20, 32, 255)
    for poly in (v_poly, i_poly):
        vi_draw.polygon(poly, fill=halo_col)
        for j in range(len(poly)):
            p1 = poly[j]
            p2 = poly[(j + 1) % len(poly)]
            vi_draw.line([p1, p2], fill=halo_col, width=halo_w)
            vi_draw.ellipse(
                [p1[0] - halo_w / 2, p1[1] - halo_w / 2,
                 p1[0] + halo_w / 2, p1[1] + halo_w / 2],
                fill=halo_col,
            )

    vi_mask = Image.new("L", (s, s), 0)
    vi_mask_draw = ImageDraw.Draw(vi_mask)
    vi_mask_draw.polygon(v_poly, fill=255)
    vi_mask_draw.polygon(i_poly, fill=255)
    vi_fill = _vertical_gradient(s, s, [
        (0.55, (245, 246, 250, 255)),
        (0.81, (226, 230, 242, 255)),
    ])
    vi_layer.paste(vi_fill, (0, 0), vi_mask)
    badge = Image.alpha_composite(badge, vi_layer)

    return badge.resize((size, size), Image.LANCZOS)


def _draw_art_deco_tower(
    draw: ImageDraw.ImageDraw,
    x: int,
    w: int,
    h: int,
    horizon_y: int,
    color: tuple,
    spire: bool = False,
) -> None:
    """Draw a stepped modern Miami / Art Deco tower silhouette."""
    draw.rectangle([x, horizon_y - h, x + w, horizon_y], fill=color)
    # Stepped crown
    crown_w = int(w * 0.64)
    crown_h = max(8, int(h * 0.16))
    cx0 = x + (w - crown_w) // 2
    draw.rectangle([cx0, horizon_y - h - crown_h, cx0 + crown_w, horizon_y - h], fill=color)
    if spire:
        mx = x + w // 2
        draw.line(
            [(mx, horizon_y - h - crown_h - 14), (mx, horizon_y - h - crown_h)],
            fill=color,
            width=2,
        )


def create_wallpaper(output_dir: str = "/usr/share/backgrounds") -> None:
    """Generate a cinematic 1080p GTA VI Leonida coastal dusk wallpaper."""
    width, height = 1920, 1080
    horizon_y = int(height * 0.65)

    # 1. Atmospheric Leonida dusk sky
    sky = _vertical_gradient(width, horizon_y, [
        (0.0, (11, 13, 22)),
        (0.30, (23, 26, 46)),
        (0.56, (58, 34, 62)),
        (0.77, (136, 56, 82)),
        (0.91, (216, 110, 92)),
        (1.0, (245, 178, 122)),
    ])
    img = Image.new("RGBA", (width, height), (11, 13, 22, 255))
    img.paste(sky, (0, 0))

    # 2. Setting sun & diffused coastal humidity glow (right-of-center)
    sun_cx = int(width * 0.57)
    sun_cy = horizon_y - 24
    sun_r = 126

    sun_glow = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(sun_glow)
    glow_draw.ellipse(
        [sun_cx - 460, sun_cy - 280, sun_cx + 460, sun_cy + 250],
        fill=(242, 138, 104, 66),
    )
    glow_draw.ellipse(
        [sun_cx - 240, sun_cy - 170, sun_cx + 240, sun_cy + 165],
        fill=(255, 206, 138, 92),
    )
    sun_glow = sun_glow.filter(ImageFilter.GaussianBlur(radius=76))
    img = Image.alpha_composite(img, sun_glow)

    sun_mask = Image.new("L", (width, height), 0)
    sun_draw = ImageDraw.Draw(sun_mask)
    sun_draw.ellipse(
        [sun_cx - sun_r, sun_cy - sun_r, sun_cx + sun_r, sun_cy + sun_r],
        fill=255,
    )
    sun_draw.rectangle([0, horizon_y, width, height], fill=0)
    sun_mask = sun_mask.filter(ImageFilter.GaussianBlur(radius=2.5))

    sun_grad = _vertical_gradient(width, height, [
        (0.46, (255, 240, 192, 255)),
        (0.58, (255, 182, 122, 255)),
        (0.66, (238, 108, 112, 255)),
    ])
    img.paste(sun_grad, (0, 0), sun_mask)

    # 3. Delicate high-altitude dusk cirrus ribbons (warm rose/amber mist)
    cirrus = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    cd = ImageDraw.Draw(cirrus)
    for x0, y0, x1, y1, col in [
        (460, 420, 1420, 434, (226, 118, 112, 34)),
        (780, 468, 1740, 484, (244, 152, 116, 40)),
        (320, 526, 1220, 540, (246, 168, 120, 38)),
        (920, 566, 1840, 582, (250, 192, 134, 42)),
    ]:
        cd.ellipse([x0, y0, x1, y1], fill=col)
    cirrus = cirrus.filter(ImageFilter.GaussianBlur(radius=20))
    img = Image.alpha_composite(img, cirrus)

    # 4. Distant Leonida barrier island & refined downtown skyline (tucked right of sun)
    skyline = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    sd = ImageDraw.Draw(skyline)
    sd.polygon([
        (0, horizon_y), (420, horizon_y - 5), (960, horizon_y - 10),
        (1420, horizon_y - 14), (1920, horizon_y - 6), (1920, horizon_y),
    ], fill=(24, 24, 38, 220))

    skyline_col = (24, 23, 39, 245)
    towers = [
        (1240, 36, 28, False), (1274, 58, 34, True), (1314, 44, 30, False),
        (1350, 82, 40, True), (1396, 56, 32, False), (1434, 96, 44, True),
        (1484, 68, 36, False), (1526, 46, 30, False), (1562, 74, 38, True),
        (1606, 50, 32, False),
    ]
    rng = random.Random(305)
    for tx, th, tw, has_spire in towers:
        _draw_art_deco_tower(sd, tx, tw, th, horizon_y, skyline_col, spire=has_spire)
        for wy in range(horizon_y - th + 10, horizon_y - 8, 12):
            for wx in range(tx + 6, tx + tw - 6, 9):
                if rng.random() < 0.20:
                    col = (247, 200, 115, 78) if rng.random() < 0.76 else (54, 214, 195, 65)
                    sd.rectangle([wx, wy, wx + 2, wy + 2], fill=col)

    # Soft horizon haze blending base of distant skyline into dusk air
    haze_band = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    ImageDraw.Draw(haze_band).rectangle(
        [0, horizon_y - 26, width, horizon_y + 4],
        fill=(218, 128, 102, 34),
    )
    haze_band = haze_band.filter(ImageFilter.GaussianBlur(radius=14))
    img = Image.alpha_composite(img, skyline)
    img = Image.alpha_composite(img, haze_band)

    # 5. Deep coastal ocean + organic golden-coral sun reflection shimmer
    ocean = _vertical_gradient(width, height - horizon_y, [
        (0.0, (30, 27, 46, 255)),
        (0.24, (19, 20, 34, 255)),
        (0.62, (12, 14, 24, 255)),
        (1.0, (8, 9, 16, 255)),
    ])
    img.paste(ocean, (0, horizon_y))

    shimmer_glow = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    sh_d = ImageDraw.Draw(shimmer_glow)
    sh_d.polygon([
        (sun_cx - 105, horizon_y), (sun_cx + 105, horizon_y),
        (sun_cx + 205, height), (sun_cx - 205, height),
    ], fill=(240, 144, 112, 36))
    shimmer_glow = shimmer_glow.filter(ImageFilter.GaussianBlur(radius=38))
    img = Image.alpha_composite(img, shimmer_glow)

    ripples = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    rd = ImageDraw.Draw(ripples)
    for i in range(1, 52):
        t = i / 52.0
        ry = horizon_y + int((t ** 1.45) * (height - horizon_y - 54))
        spread = 88 + 145 * t
        segments = 2 + int(rng.random() * 3)
        for _ in range(segments):
            cx_seg = sun_cx + int((rng.random() - 0.5) * spread * 1.4)
            seg_len = int((18 + rng.random() * 68) * (1.0 - 0.45 * t))
            alpha = max(12, int((95 - i * 1.4) * (0.45 + 0.55 * rng.random())))
            col = (248, 192, 132, alpha) if rng.random() < 0.62 else (238, 120, 124, alpha)
            rd.line([(cx_seg - seg_len // 2, ry), (cx_seg + seg_len // 2, ry)], fill=col, width=2)
    ripples = ripples.filter(ImageFilter.GaussianBlur(radius=2.4))
    img = Image.alpha_composite(img, ripples)

    draw = ImageDraw.Draw(img)
    draw.line([(0, horizon_y), (width, horizon_y)], fill=(245, 178, 122, 95), width=1)

    # 6. Graceful right-edge foreground coconut palms (left desktop icon zone stays 100% open)
    palm_fg = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    pd = ImageDraw.Draw(palm_fg)
    _draw_palm_tree(pd, width - 58, height, width - 188, int(height * 0.30), 1.55, (10, 11, 18, 255))
    _draw_palm_tree(pd, width - 208, height, width - 310, int(height * 0.47), 1.12, (13, 14, 23, 246))
    img = Image.alpha_composite(img, palm_fg)

    # 7. Subtle left + bottom vignette so desktop icons and 44px taskbar read cleanly
    vig = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    left_mask = Image.new("L", (460, 1))
    lm_pix = left_mask.load()
    for x in range(460):
        lm_pix[x, 0] = int(95 * (1.0 - x / 459.0) ** 1.9)
    left_mask = left_mask.resize((460, height), Image.BILINEAR)
    vig.paste(Image.new("RGBA", (460, height), (11, 13, 21, 255)), (0, 0), left_mask)

    bot_mask = Image.new("L", (1, 110))
    bm_pix = bot_mask.load()
    for y in range(110):
        bm_pix[0, y] = int(125 * (y / 109.0) ** 1.7)
    bot_mask = bot_mask.resize((width, 110), Image.BILINEAR)
    vig.paste(Image.new("RGBA", (width, 110), (10, 11, 18, 255)), (0, height - 110), bot_mask)
    img = Image.alpha_composite(img, vig)

    try:
        os.makedirs(output_dir, exist_ok=True)
        img.convert("RGB").save(
            os.path.join(output_dir, "vice_neon.jpg"),
            "JPEG",
            quality=94,
        )
        print("[*] Wallpaper generated successfully.")
    except OSError as e:
        print(f"[!] Failed to save wallpaper: {e}", file=sys.stderr)
        raise


def create_icon(output_dir: str = "/usr/share/pixmaps") -> None:
    """Generate the GTA VI x Debian Swirl logos in /usr/share/pixmaps."""
    logo = create_gta6_debian_logo(512, with_badge=True)
    try:
        os.makedirs(output_dir, exist_ok=True)
        logo.save(os.path.join(output_dir, "vice-debian-gta6.png"), "PNG")
        logo.save(os.path.join(output_dir, "vice-app.png"), "PNG")
        print("[*] Icon generated successfully.")
    except OSError as e:
        print(f"[!] Failed to save icon: {e}", file=sys.stderr)
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description="GTA VI OS Asset Generator")
    parser.add_argument(
        "--wallpaper-dir",
        type=str,
        default="/usr/share/backgrounds",
        help="Output directory for wallpaper",
    )
    parser.add_argument(
        "--icon-dir",
        type=str,
        default="/usr/share/pixmaps",
        help="Output directory for icon",
    )
    args = parser.parse_args()

    create_wallpaper(args.wallpaper_dir)
    create_icon(args.icon_dir)


if __name__ == "__main__":
    main()
