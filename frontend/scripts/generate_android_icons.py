from PIL import Image
import os
import shutil

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.dirname(SCRIPT_DIR)
SOURCE = os.path.join(FRONTEND_DIR, 'public', 'symbol.png')
RES_DIR = os.path.join(FRONTEND_DIR, 'android', 'app', 'src', 'main', 'res')
BG_COLOR = (0x48, 0x4f, 0x5f, 255)

LAUNCHER_SIZES = {
    'mipmap-mdpi': 48,
    'mipmap-hdpi': 72,
    'mipmap-xhdpi': 96,
    'mipmap-xxhdpi': 144,
    'mipmap-xxxhdpi': 192,
}

FOREGROUND_SIZES = {
    'mipmap-mdpi': 108,
    'mipmap-hdpi': 162,
    'mipmap-xhdpi': 216,
    'mipmap-xxhdpi': 324,
    'mipmap-xxxhdpi': 432,
}

src = Image.open(SOURCE).convert('RGBA')

for folder, size in LAUNCHER_SIZES.items():
    out_dir = os.path.join(RES_DIR, folder)
    os.makedirs(out_dir, exist_ok=True)

    bg = Image.new('RGBA', (size, size), BG_COLOR)
    icon = src.resize((size, size), Image.LANCZOS)
    bg.paste(icon, (0, 0), icon)
    composite = bg.convert('RGB')

    launcher_path = os.path.join(out_dir, 'ic_launcher.png')
    composite.save(launcher_path, 'PNG')
    print(f'  {launcher_path}')

    round_path = os.path.join(out_dir, 'ic_launcher_round.png')
    shutil.copy2(launcher_path, round_path)
    print(f'  {round_path}')

for folder, size in FOREGROUND_SIZES.items():
    out_dir = os.path.join(RES_DIR, folder)
    os.makedirs(out_dir, exist_ok=True)

    inner = int(size * 0.66)
    offset = (size - inner) // 2

    canvas = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    icon = src.resize((inner, inner), Image.LANCZOS)
    canvas.paste(icon, (offset, offset), icon)

    fg_path = os.path.join(out_dir, 'ic_launcher_foreground.png')
    canvas.save(fg_path, 'PNG')
    print(f'  {fg_path}')

print('\nDone.')
