#!/usr/bin/env python3
"""Regenerate Android launcher icons (foreground + legacy) with B at ~40% of canvas."""
import os
from PIL import Image, ImageDraw

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE_PATH = os.path.join(REPO_ROOT, "frontend/android/app/src/main/res")

DENSITIES = {"mdpi": 108, "hdpi": 162, "xhdpi": 216, "xxhdpi": 324, "xxxhdpi": 432}
TARGET_RATIO = 0.40  # B occupies 40% of canvas — smaller than current 50% which still feels big on Samsung
BG_COLOR = (0x32, 0x3A, 0x4E, 255)  # #323A4E from ic_launcher_background.xml

def extract_b(src_path):
    img = Image.open(src_path).convert("RGBA")
    bbox = img.split()[3].getbbox()
    if not bbox:
        raise ValueError(f"No non-transparent pixels in {src_path}")
    return img.crop(bbox)

def regen_foreground(density, size, source_b):
    dst = os.path.join(BASE_PATH, f"mipmap-{density}", "ic_launcher_foreground.png")
    b = source_b.copy()
    b.thumbnail((int(size * TARGET_RATIO), int(size * TARGET_RATIO)), Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ox, oy = (size - b.width) // 2, (size - b.height) // 2
    canvas.paste(b, (ox, oy), b)
    canvas.save(dst, "PNG", optimize=True)
    return dst

def regen_legacy(density, size, is_round):
    fname = "ic_launcher_round.png" if is_round else "ic_launcher.png"
    dst = os.path.join(BASE_PATH, f"mipmap-{density}", fname)
    fg = Image.open(os.path.join(BASE_PATH, f"mipmap-{density}", "ic_launcher_foreground.png")).convert("RGBA")
    bg = Image.new("RGBA", (size, size), BG_COLOR)
    composite = Image.alpha_composite(bg, fg)
    if is_round:
        mask = Image.new("L", (size, size), 0)
        ImageDraw.Draw(mask).ellipse([0, 0, size - 1, size - 1], fill=255)
        result = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        result.paste(composite, (0, 0), mask)
        composite = result
    composite.save(dst, "PNG", optimize=True)
    return dst

def main():
    source = extract_b(os.path.join(BASE_PATH, "mipmap-xxxhdpi", "ic_launcher_foreground.png"))
    print(f"Source B cropped: {source.size}")
    written = 0
    for density, size in DENSITIES.items():
        regen_foreground(density, size, source); written += 1
        regen_legacy(density, size, False); written += 1
        regen_legacy(density, size, True); written += 1
        print(f"  {density}: foreground + launcher + launcher_round")
    print(f"\n{written} files written.")

    print("\nVerification:")
    for density, size in DENSITIES.items():
        fg = Image.open(os.path.join(BASE_PATH, f"mipmap-{density}", "ic_launcher_foreground.png"))
        bbox = fg.split()[3].getbbox()
        ratio = ((bbox[2] - bbox[0]) / size) * 100
        assert fg.size == (size, size), f"{density} foreground wrong size"
        assert 35 < ratio < 45, f"{density} B ratio {ratio:.1f}% outside 35-45"
        print(f"  {density}: {size}x{size}, B ratio {ratio:.1f}% ✓")
    print("\nAll good.")

if __name__ == "__main__":
    main()
