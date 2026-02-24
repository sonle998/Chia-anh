#!/usr/bin/env python3
"""Split scanned manga spreads (2 pages in 1 image) into single pages.

Default export order is right-to-left (Japanese manga reading order).
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable, Sequence

import numpy as np
from PIL import Image


SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff", ".bmp"}


def find_fold_x(
    gray: np.ndarray,
    search_ratio: float = 0.22,
    neighborhood: int = 8,
) -> int:
    """Estimate the center fold x-coordinate.

    The detector searches around the image center and scores each column by how
    different it is from immediate neighbors. This works when the fold/gutter is
    either brighter or darker than nearby content.
    """

    h, w = gray.shape
    column_mean = gray.mean(axis=0)

    center = w // 2
    radius = max(5, int(w * search_ratio))
    start = max(neighborhood + 1, center - radius)
    end = min(w - neighborhood - 1, center + radius)
    if start >= end:
        return center

    scores = np.zeros(w, dtype=np.float32)
    for x in range(start, end):
        left_avg = column_mean[x - neighborhood : x].mean()
        right_avg = column_mean[x + 1 : x + 1 + neighborhood].mean()
        local_avg = 0.5 * (left_avg + right_avg)
        delta = column_mean[x] - local_avg
        scores[x] = abs(delta)

    smooth = np.convolve(scores[start:end], np.ones(7) / 7.0, mode="same")
    best_idx = int(np.argmax(smooth))
    return start + best_idx



def split_spread(
    image: Image.Image,
    split_x: int,
    gutter: int = 0,
) -> tuple[Image.Image, Image.Image]:
    """Split image into (left_page, right_page)."""

    width, height = image.size
    split_x = int(np.clip(split_x, 1, width - 1))
    gutter = max(0, int(gutter))

    left_end = max(1, split_x - gutter)
    right_start = min(width - 1, split_x + gutter)

    left = image.crop((0, 0, left_end, height))
    right = image.crop((right_start, 0, width, height))
    return left, right



def collect_images(paths: Sequence[str]) -> Iterable[Path]:
    for raw in paths:
        p = Path(raw)
        if p.is_dir():
            for child in sorted(p.iterdir()):
                if child.suffix.lower() in SUPPORTED_EXTENSIONS:
                    yield child
        elif p.is_file():
            yield p
        else:
            raise FileNotFoundError(f"Input not found: {p}")



def process_file(
    input_path: Path,
    output_dir: Path,
    forced_split_x: int | None,
    gutter: int,
    rtl_order: bool,
    search_ratio: float,
) -> None:
    with Image.open(input_path) as img:
        gray = np.asarray(img.convert("L"), dtype=np.float32)
        split_x = forced_split_x if forced_split_x is not None else find_fold_x(gray, search_ratio=search_ratio)
        left, right = split_spread(img, split_x, gutter=gutter)

        output_dir.mkdir(parents=True, exist_ok=True)
        stem = input_path.stem
        suffix = input_path.suffix.lower() or ".png"

        pages = [("left", left), ("right", right)]
        if rtl_order:
            pages = [("right", right), ("left", left)]

        for index, (label, page) in enumerate(pages, start=1):
            out_name = f"{stem}_{index:02d}_{label}{suffix}"
            page.save(output_dir / out_name)

        print(f"{input_path} -> split_x={split_x}, output={output_dir}")



def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Split manga spreads (2 pages in 1 scan) into single pages."
    )
    parser.add_argument(
        "inputs",
        nargs="+",
        help="Input image file(s) or directory(ies).",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        default="split_output",
        help="Output folder (default: split_output).",
    )
    parser.add_argument(
        "--split-x",
        type=int,
        default=None,
        help="Force split position X (pixels). If omitted, auto-detect near center fold.",
    )
    parser.add_argument(
        "--gutter",
        type=int,
        default=0,
        help="Pixels to discard around fold on both sides.",
    )
    parser.add_argument(
        "--ltr",
        action="store_true",
        help="Export in left-to-right order (default is right-to-left).",
    )
    parser.add_argument(
        "--search-ratio",
        type=float,
        default=0.22,
        help="Auto-detection search range around center (fraction of width, default: 0.22).",
    )
    return parser



def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    out_dir = Path(args.output_dir)
    rtl_order = not args.ltr

    for image_path in collect_images(args.inputs):
        process_file(
            input_path=image_path,
            output_dir=out_dir,
            forced_split_x=args.split_x,
            gutter=args.gutter,
            rtl_order=rtl_order,
            search_ratio=args.search_ratio,
        )


if __name__ == "__main__":
    main()
