#!/usr/bin/env python3
"""
Kindle Custom Screensaver Converter
------------------------------------
Converts a folder of photos into Kindle-compatible screensaver images:
resized/cropped to the device's screensaver resolution, converted to
grayscale, and remapped onto the Kindle's exact indexed color palette
WITHOUT dithering (see README's Troubleshooting section for why the
naive Pillow .quantize() approach produces a noisy/embossed result).

Usage:
    1. Edit the settings below to match your paths and device resolution.
    2. Run: python3 batch_convert.py

Requires: Pillow, numpy
    pip install Pillow numpy --break-system-packages
"""

import os
import numpy as np
from PIL import Image

# --- Settings (edit these) ---
source_folder = "/path/to/your/photos"
original_palette_file = "/path/to/kindle_screensavers/bg_ss00.png"
output_folder = "kindle_screensavers_new"
target_size = (1072, 1448)   # (width, height) — match your Kindle's screensaver resolution
start_number = 20            # first output file will be bg_ss{start_number}.png

# --- Setup ---
os.makedirs(output_folder, exist_ok=True)
original = Image.open(original_palette_file)

# Build the list of actual grayscale values used in the original palette,
# so we can map each new pixel to the nearest existing shade ourselves
# (avoids Pillow's built-in dithering, which distorts flat/illustrated images).
used_colors = original.getcolors(maxcolors=100000)
max_index = max(idx for count, idx in used_colors)
raw_palette = original.getpalette()
gray_values = np.array([raw_palette[i * 3] for i in range(max_index + 1)], dtype=np.int16)


def apply_palette_no_dither(gray_img):
    """Map a grayscale image onto the Kindle's palette with nearest-value matching only."""
    arr = np.array(gray_img, dtype=np.int16)
    diffs = np.abs(arr[..., None] - gray_values[None, None, :])
    indices = np.argmin(diffs, axis=-1).astype(np.uint8)
    out = Image.fromarray(indices, mode="P")
    out.putpalette(raw_palette)
    return out


valid_extensions = (".jpg", ".jpeg", ".png", ".bmp", ".webp")
files = sorted(f for f in os.listdir(source_folder) if f.lower().endswith(valid_extensions))

if not files:
    print(f"No images found in {source_folder}")

for i, filename in enumerate(files):
    src_path = os.path.join(source_folder, filename)
    src = Image.open(src_path)

    # Resize + center-crop to fill target size without distortion
    src_ratio = src.width / src.height
    target_ratio = target_size[0] / target_size[1]

    if src_ratio > target_ratio:
        new_height = target_size[1]
        new_width = int(new_height * src_ratio)
    else:
        new_width = target_size[0]
        new_height = int(new_width / src_ratio)

    src = src.resize((new_width, new_height), Image.LANCZOS)

    left = (new_width - target_size[0]) // 2
    top = (new_height - target_size[1]) // 2
    src = src.crop((left, top, left + target_size[0], top + target_size[1]))

    # Grayscale, then map onto the Kindle's exact palette
    src = src.convert("L")
    src_indexed = apply_palette_no_dither(src)

    # Naming pattern the Kindle expects: bg_ssNN.png
    out_name = f"bg_ss{start_number + i:02d}.png"
    src_indexed.save(os.path.join(output_folder, out_name))
    print(f"{filename} -> {out_name}")

print("Done!")
