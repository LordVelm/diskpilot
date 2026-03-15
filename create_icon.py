"""Generate app icon for DiskPart GUI — a stylized hard drive."""

from PIL import Image, ImageDraw

SIZES = [16, 24, 32, 48, 64, 128, 256]


def draw_icon(size: int) -> Image.Image:
    """Draw a hard-drive icon at the given pixel size."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    s = size  # shorthand

    pad = max(1, round(s * 0.06))
    r = max(2, round(s * 0.12))  # corner radius

    # --- Main body: rounded rectangle (dark blue-grey) ---
    body_color = (40, 44, 52)       # dark charcoal
    d.rounded_rectangle([pad, pad, s - pad - 1, s - pad - 1], radius=r, fill=body_color)

    # --- Top accent bar (teal/cyan) ---
    bar_h = max(2, round(s * 0.18))
    accent = (0, 168, 150)          # teal matching CustomTkinter accent vibe
    d.rounded_rectangle(
        [pad, pad, s - pad - 1, pad + bar_h],
        radius=r, fill=accent,
    )
    # Square off bottom corners of the bar
    d.rectangle([pad, pad + bar_h - r, s - pad - 1, pad + bar_h], fill=accent)

    # --- Platter circle (center of body) ---
    cx, cy = s // 2, s // 2 + round(s * 0.06)
    platter_r = round(s * 0.22)
    platter_color = (58, 63, 75)
    d.ellipse(
        [cx - platter_r, cy - platter_r, cx + platter_r, cy + platter_r],
        fill=platter_color, outline=(80, 86, 100), width=max(1, round(s * 0.02)),
    )

    # --- Spindle dot (center) ---
    dot_r = max(1, round(s * 0.05))
    d.ellipse(
        [cx - dot_r, cy - dot_r, cx + dot_r, cy + dot_r],
        fill=accent,
    )

    # --- Bottom-right LED indicator ---
    led_r = max(1, round(s * 0.04))
    led_x = s - pad - round(s * 0.14)
    led_y = s - pad - round(s * 0.12)
    d.ellipse(
        [led_x - led_r, led_y - led_r, led_x + led_r, led_y + led_r],
        fill=(80, 250, 123),  # green LED
    )

    return img


def main():
    # Pillow ICO plugin: pass all frames as append_images, each at its native size
    frames = [draw_icon(sz) for sz in SIZES]
    # Save by providing the largest as the base and all as append_images
    largest = frames[-1]  # 256x256
    largest.save(
        "icon.ico",
        format="ICO",
        append_images=frames[:-1],
    )
    print("Created icon.ico with sizes:", SIZES)


if __name__ == "__main__":
    main()
