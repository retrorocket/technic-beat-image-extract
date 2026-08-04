#!/usr/bin/env python3
"""
Technic Beat (PS2) omake/xxx.gsm extractor
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image


def decode_gsm(input_path: Path, output_path: Path, crop: bool) -> None:
    data = input_path.read_bytes()

    if len(data) < 0x40400:
        raise ValueError(f"File is too small: {len(data):#x} bytes")

    palette = np.frombuffer(data[:0x400], dtype=np.uint8).reshape(256, 4).copy()

    # PS2 GS CSM1 CLUT permutation.
    for base in range(0, 256, 32):
        a = palette[base + 8:base + 16].copy()
        b = palette[base + 16:base + 24].copy()
        palette[base + 8:base + 16] = b
        palette[base + 16:base + 24] = a

    # Important: upload begins at 0x400. The 0x48-byte zero area is part
    # of the 256x256 PSMCT32 transfer and must not be skipped.
    upload = np.frombuffer(data[0x400:0x400 + 0x40000], dtype=np.uint8)
    if upload.size != 0x40000:
        raise ValueError("Incomplete GSM texture upload area")

    width = height = 512
    indices = np.empty(width * height, dtype=np.uint8)

    for y in range(height):
        for x in range(width):
            block_location = (y & ~0x0F) * width + (x & ~0x0F) * 2
            swap_selector = (((y + 2) >> 2) & 1) * 4
            pos_y = (((y & ~3) >> 1) + (y & 1)) & 7
            column_location = pos_y * width * 2 + ((x + swap_selector) & 7) * 4
            byte_num = ((y >> 1) & 1) + ((x >> 2) & 2)
            indices[y * width + x] = upload[
                block_location + column_location + byte_num
            ]

    indices = indices.reshape(height, width)
    rgba = palette[indices].copy()

    # GS alpha range is 0x00–0x80.
    rgba[..., 3] = np.minimum(
        rgba[..., 3].astype(np.uint16) * 2, 255
    ).astype(np.uint8)

    image = Image.fromarray(rgba, "RGBA")

    if crop:
        bbox = image.getbbox()
        if bbox:
            image = image.crop(bbox)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Extract Technic Beat GSM images as PNG."
    )
    parser.add_argument("input", type=Path, help="Input .gsm file")
    parser.add_argument("output", type=Path, help="Output .png file")
    parser.add_argument(
        "--crop",
        action="store_true",
        help="Crop transparent borders",
    )
    args = parser.parse_args()

    try:
        decode_gsm(args.input, args.output, args.crop)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
