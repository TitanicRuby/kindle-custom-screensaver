#!/usr/bin/env python3
"""
Kindle Custom Screensaver Converter
------------------------------------
Converts a folder of photos into Kindle-compatible screensaver images:
resized/cropped to the device's screensaver resolution, converted to
grayscale, and remapped onto the Kindle's exact indexed color palette
WITHOUT dithering (see README's Troubleshooting section for why the
naive Pillow .quantize() approach produces a noisy/embossed result).

Two modes:
  "add"     - keep the existing screensavers, add your photos after them.
  "replace" - meant to fully take over the rotation. Numbers your photos
              from 0, and writes a delete_originals.sh helper script
              listing the original files to remove from the Kindle
              (you run that yourself, over SSH, after checking it).

The naming pattern (e.g. "bg_ss00.png") is auto-detected from a local
folder containing your downloaded originals, so this isn't hardcoded
to one specific Kindle model.

Usage:
    1. Edit the settings below.
    2. Run: python3 batch_convert.py

Requires: Pillow, numpy
    pip install Pillow numpy --break-system-packages
"""

import os
import re
import numpy as np
from PIL import Image

# --- Settings (edit these) ---
source_folder = "/path/to/your/photos"
originals_folder = "/path/to/kindle_screensavers"  # local downloaded copy of the Kindle's screensaver folder
output_folder = "kindle_screensavers_new"
target_size = (1072, 1448)   # (width, height) - match your Kindle's screensaver resolution

mode = "add"          # "add" = keep existing, append after them
                       # "replace" = renumber from 0, meant to fully replace the rotation
start_number = None   # only used when mode == "add". Leave as None to auto-continue after the
                       # highest index found in originals_folder (recommended - see README on
                       # keeping originals_folder in sync). Set a number to override manually.

naming_prefix = None       # e.g. "bg_ss" - leave None to auto-detect from originals_folder
palette_reference = None   # a specific filename in originals_folder to source the palette from
                            # leave None to just use the first detected file

remote_screensaver_path = "/usr/share/blanket/screensaver/"  # only used to write delete_originals.sh in "replace" mode


# --- Step 1: detect the existing naming pattern from your downloaded originals ---
def detect_pattern(folder):
    groups = {}
    for fname in os.listdir(folder):
        m = re.match(r"^(.*?)(\d+)(\.[A-Za-z0-9]+)$", fname)
        if not m:
            continue
        prefix, digits, ext = m.groups()
        key = (prefix, len(digits), ext.lower())
        groups.setdefault(key, []).append(fname)
    if not groups:
        raise RuntimeError(f"No numbered image files found in {folder} to detect a naming pattern from.")
    best_key = max(groups, key=lambda k: len(groups[k]))
    return best_key, groups


(detected_prefix, detected_width, detected_ext), groups = detect_pattern(originals_folder)

if naming_prefix is not None:
    matches = [k for k in groups if k[0] == naming_prefix]
    if not matches:
        raise RuntimeError(f"No files matching prefix '{naming_prefix}' found in {originals_folder}")
    prefix, width, ext = matches[0]
else:
    prefix, width, ext = detected_prefix, detected_width, detected_ext

matched_files = sorted(groups[(prefix, width, ext)])
print(f"Detected naming pattern: {prefix}{{{width} digits}}{ext}  ({len(matched_files)} files found)")
if naming_prefix is None:
    print("If this looks wrong (e.g. it picked a kids-mode or unrelated set instead of the "
          "main rotation), set naming_prefix explicitly at the top of the script and re-run.")

# Work out the highest index currently used by this pattern (needed to auto-continue numbering)
file_re = re.compile(r"^" + re.escape(prefix) + r"(\d{" + str(width) + r"})" + re.escape(ext) + r"$")
existing_indices = [int(file_re.match(f).group(1)) for f in matched_files if file_re.match(f)]
highest_existing_index = max(existing_indices) if existing_indices else -1

# --- Step 2: load the palette to match against ---
palette_path = os.path.join(originals_folder, palette_reference or matched_files[0])
original = Image.open(palette_path)
used_colors = original.getcolors(maxcolors=100000)
max_palette_index = max(idx for count, idx in used_colors)
raw_palette = original.getpalette()
gray_values = np.array([raw_palette[i * 3] for i in range(max_palette_index + 1)], dtype=np.int16)


def apply_palette_no_dither(gray_img):
    """Map a grayscale image onto the Kindle's palette with nearest-value matching only (no dithering)."""
    arr = np.array(gray_img, dtype=np.int16)
    diffs = np.abs(arr[..., None] - gray_values[None, None, :])
    indices = np.argmin(diffs, axis=-1).astype(np.uint8)
    out = Image.fromarray(indices, mode="P")
    out.putpalette(raw_palette)
    return out


# --- Step 3: gather your photos ---
os.makedirs(output_folder, exist_ok=True)
valid_extensions = (".jpg", ".jpeg", ".png", ".bmp", ".webp")
photos = sorted(f for f in os.listdir(source_folder) if f.lower().endswith(valid_extensions))
if not photos:
    raise RuntimeError(f"No images found in {source_folder}")

if mode == "add":
    if start_number is None:
        first_index = highest_existing_index + 1
        print(f"Auto-continuing after highest detected index ({highest_existing_index}) -> starting at {first_index}")
    else:
        first_index = start_number
elif mode == "replace":
    first_index = 0
else:
    raise ValueError("mode must be 'add' or 'replace'")

max_representable = 10 ** width - 1
if first_index + len(photos) - 1 > max_representable:
    raise RuntimeError(
        f"{len(photos)} photo(s) starting at index {first_index} won't fit in {width}-digit "
        f"numbering (max index is {max_representable}). Reduce the photo count, lower "
        f"start_number, or split into batches."
    )

planned_names = [f"{prefix}{first_index + i:0{width}d}{ext}" for i in range(len(photos))]

# collision check - don't silently overwrite anything already in the output folder
existing_output = set(os.listdir(output_folder))
collisions = [n for n in planned_names if n in existing_output]
if collisions:
    raise RuntimeError(
        f"These output files already exist in {output_folder} and would be overwritten: {collisions}\n"
        f"Move/rename/delete them first, or change start_number/output_folder."
    )

# --- Step 4: convert each photo ---
for photo_name, out_name in zip(photos, planned_names):
    src = Image.open(os.path.join(source_folder, photo_name))

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

    src = src.convert("L")
    src_indexed = apply_palette_no_dither(src)
    src_indexed.save(os.path.join(output_folder, out_name))
    print(f"{photo_name} -> {out_name}")

print(f"\nDone! {len(photos)} image(s) written to {output_folder}/ using mode='{mode}'.")

# --- Step 5: in "replace" mode, generate a helper script to remove the ORIGINALS on the Kindle ---
if mode == "replace":
    delete_script_path = os.path.join(output_folder, "delete_originals.sh")
    with open(delete_script_path, "w") as f:
        f.write("#!/bin/sh\n")
        f.write("# Run this ON THE KINDLE over SSH to remove the original screensavers.\n")
        f.write("# REVIEW THE FILE LIST BELOW BEFORE RUNNING - this deletes files.\n")
        f.write(f"# Your originals are already backed up locally at: {originals_folder}\n\n")
        f.write("# Uses 'rm -f' so an already-missing file won't stop the script -\n")
        f.write("# that would otherwise leave the filesystem stuck read-write.\n")
        f.write("mntroot rw\n")
        for fname in matched_files:
            f.write(f'rm -fv "{remote_screensaver_path}{fname}"\n')
        f.write("mntroot ro\n")
    print(f"\nGenerated {delete_script_path}")
    print(f"It will delete {len(matched_files)} original file(s) from the Kindle:")
    print(f"  {matched_files}")
    print("Copy it to the Kindle, READ IT, then run it over SSH — it will NOT run itself.")
