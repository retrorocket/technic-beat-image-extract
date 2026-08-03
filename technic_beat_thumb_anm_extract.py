#!/usr/bin/env python3
"""
Technic Beat (PS2) menu/thumb.anm extractor
"""

from __future__ import annotations

import argparse
import csv
import struct
import sys
from pathlib import Path


class FormatError(RuntimeError):
    pass


def ps2_clut_index(index: int) -> int:
    """Undo the 8-entry/16-entry swap used by PS2 8-bit CLUTs."""
    return (index & 0xE7) | ((index & 0x08) << 1) | ((index & 0x10) >> 1)


def decompress_rle(data: bytes, offset: int, expected_size: int) -> tuple[bytes, int]:
    """
    Decode the RLE routine observed in the game.

    Header:
      u16 little-endian output_size_in_16_byte_units

    Packets:
      control bit 7 = 1:
        repeat the next byte (control & 0x7F) + 2 times
      control bit 7 = 0:
        copy control + 1 literal bytes following the control byte
    """
    if offset < 0 or offset + 2 > len(data):
        raise FormatError(f"RLE block offset 0x{offset:X} is outside the file")

    declared_size = struct.unpack_from("<H", data, offset)[0] << 4
    if declared_size != expected_size:
        raise FormatError(
            f"RLE block at 0x{offset:X} declares {declared_size} bytes; "
            f"expected {expected_size}"
        )

    src = offset + 2
    out = bytearray()

    while len(out) < declared_size:
        if src >= len(data):
            raise FormatError(
                f"unexpected end of file while decoding block at 0x{offset:X}"
            )

        control = data[src]
        src += 1

        if control & 0x80:
            if src >= len(data):
                raise FormatError("missing repeat value")
            value = data[src]
            src += 1
            count = (control & 0x7F) + 2
            out.extend(bytes([value]) * min(count, declared_size - len(out)))
        else:
            count = control + 1
            if src + count > len(data):
                raise FormatError("literal packet exceeds file")
            take = min(count, declared_size - len(out))
            out.extend(data[src:src + take])
            src += count

    return bytes(out), src - offset


def decode_alpha(value: int, mode: str) -> int:
    if mode == "ps2":
        # GS alpha normally uses 0x80 as fully opaque.
        return min(255, value * 2)
    if mode == "raw":
        return value
    return 255


def parse_header(data: bytes) -> dict[str, int]:
    if len(data) < 0x18:
        raise FormatError("file is too small")

    version, frame_count, width, height, total_size, data_size, palette_base, data_base = (
        struct.unpack_from("<HHHHIIII", data, 0)
    )

    if total_size != len(data):
        raise FormatError(
            f"header file size 0x{total_size:X} does not match actual "
            f"size 0x{len(data):X}"
        )
    if frame_count <= 0 or width <= 0 or height <= 0:
        raise FormatError("invalid frame count or dimensions")
    if palette_base + frame_count * 0x400 != data_base:
        raise FormatError(
            "unexpected palette/data layout; this may not be menu/thumb.anm"
        )
    if data_base + data_size != len(data):
        raise FormatError("compressed-data size does not reach the end of the file")

    return {
        "version": version,
        "frame_count": frame_count,
        "width": width,
        "height": height,
        "total_size": total_size,
        "data_size": data_size,
        "palette_base": palette_base,
        "data_base": data_base,
    }


def build_palette(
    raw_palette: bytes,
    clut_swizzle: bool,
    alpha_mode: str,
) -> list[tuple[int, int, int, int]]:
    if len(raw_palette) != 0x400:
        raise FormatError("palette is not 1024 bytes")

    palette = []
    for index in range(256):
        source_index = ps2_clut_index(index) if clut_swizzle else index
        r, g, b, a = raw_palette[source_index * 4:source_index * 4 + 4]
        palette.append((r, g, b, decode_alpha(a, alpha_mode)))
    return palette


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Extract correctly coloured PNG cards from Technic Beat PS2 menu/thumb.anm"
    )
    parser.add_argument("thumb_anm", type=Path, help="menu/thumb.anm")
    parser.add_argument(
        "-o", "--output-dir", type=Path, default=Path("thumb_extracted"),
        help="output directory (default: thumb_extracted)",
    )
    parser.add_argument(
        "--no-clut-swizzle", action="store_true",
        help="disable PS2 CLUT permutation (normally produces wrong colours)",
    )
    parser.add_argument(
        "--alpha", choices=["ps2", "raw", "opaque"], default="ps2",
        help="alpha conversion (default: ps2, where 0x80 is opaque)",
    )
    parser.add_argument(
        "--contact-sheet", action="store_true",
        help="also create contact_sheet.png",
    )
    parser.add_argument(
        "--scale", type=int, default=1,
        help="integer PNG scale using nearest-neighbour (default: 1)",
    )
    args = parser.parse_args()

    if args.scale < 1:
        parser.error("--scale must be at least 1")

    try:
        from PIL import Image, ImageDraw
    except ImportError:
        print("Pillow is required: pip install pillow", file=sys.stderr)
        return 1

    try:
        data = args.thumb_anm.read_bytes()
        header = parse_header(data)
        output_size = header["width"] * header["height"]

        args.output_dir.mkdir(parents=True, exist_ok=True)
        extracted = []
        manifest_rows = []

        for frame_index in range(header["frame_count"]):
            table_offset = 0x18 + frame_index * 8
            compressed_size, relative_offset = struct.unpack_from(
                "<II", data, table_offset
            )
            block_offset = header["data_base"] + relative_offset

            pixels, consumed = decompress_rle(data, block_offset, output_size)
            if consumed != compressed_size:
                raise FormatError(
                    f"frame {frame_index}: table size 0x{compressed_size:X}, "
                    f"decoder consumed 0x{consumed:X}"
                )

            palette_offset = header["palette_base"] + frame_index * 0x400
            palette = build_palette(
                data[palette_offset:palette_offset + 0x400],
                clut_swizzle=not args.no_clut_swizzle,
                alpha_mode=args.alpha,
            )

            image = Image.new(
                "RGBA", (header["width"], header["height"])
            )
            image.putdata([palette[value] for value in pixels])

            if args.scale != 1:
                image = image.resize(
                    (image.width * args.scale, image.height * args.scale),
                    Image.Resampling.NEAREST,
                )

            filename = f"{frame_index:02d}.png"
            image.save(args.output_dir / filename)
            extracted.append((frame_index, image.copy()))

            manifest_rows.append({
                "frame": frame_index,
                "png": filename,
                "palette_offset": f"0x{palette_offset:X}",
                "compressed_offset": f"0x{block_offset:X}",
                "compressed_size": f"0x{compressed_size:X}",
                "decompressed_size": f"0x{len(pixels):X}",
            })

        with (args.output_dir / "manifest.csv").open(
            "w", newline="", encoding="utf-8-sig"
        ) as fp:
            writer = csv.DictWriter(fp, fieldnames=manifest_rows[0].keys())
            writer.writeheader()
            writer.writerows(manifest_rows)

        if args.contact_sheet:
            columns = 6
            label_height = 24
            tile_width = extracted[0][1].width
            tile_height = extracted[0][1].height + label_height
            rows = (len(extracted) + columns - 1) // columns

            sheet = Image.new(
                "RGBA",
                (columns * tile_width, rows * tile_height),
                (24, 24, 24, 255),
            )
            draw = ImageDraw.Draw(sheet)

            for position, (frame_index, image) in enumerate(extracted):
                x = (position % columns) * tile_width
                y = (position // columns) * tile_height
                sheet.alpha_composite(image, (x, y))
                draw.text(
                    (x + 4, y + image.height + 4),
                    f"{frame_index:02d}",
                    fill=(255, 255, 255, 255),
                )

            sheet.save(args.output_dir / "contact_sheet.png")

        print(
            f"Extracted {header['frame_count']} frames "
            f"({header['width']}x{header['height']}) to {args.output_dir}"
        )
        return 0

    except (OSError, FormatError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
