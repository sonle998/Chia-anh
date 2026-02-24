#!/usr/bin/env python3
"""Split scanned manga spreads into single pages.

- Default export order is right-to-left (Japanese manga reading order).
- Directory inputs are scanned recursively (including subfolders).
- Output files are numbered 001..N per output folder.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import Path
from typing import Iterable, Sequence

from PIL import Image


SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff", ".bmp"}


def grayscale_column_means(image: Image.Image) -> list[float]:
    gray = image.convert("L")
    width, height = gray.size
    pixels = gray.load()
    sums = [0.0] * width

    for y in range(height):
        for x in range(width):
            sums[x] += float(pixels[x, y])

    inv_h = 1.0 / max(height, 1)
    return [s * inv_h for s in sums]


def moving_average(values: list[float], window: int) -> list[float]:
    if not values or window <= 1:
        return values[:]

    window = max(1, min(window, len(values)))
    out: list[float] = []
    acc = sum(values[:window])
    out.append(acc / window)

    for i in range(window, len(values)):
        acc += values[i] - values[i - window]
        out.append(acc / window)

    pad_left = window // 2
    pad_right = len(values) - len(out) - pad_left
    return [out[0]] * pad_left + out + [out[-1]] * max(0, pad_right)


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    arr = sorted(values)
    idx = int((len(arr) - 1) * p)
    return arr[idx]


def find_fold_x(
    image: Image.Image,
    search_ratio: float = 0.22,
    neighborhood: int = 8,
) -> tuple[int, float]:
    """Estimate center fold x-coordinate and fold prominence score."""

    width, _ = image.size
    column_mean = grayscale_column_means(image)

    center = width // 2
    radius = max(5, int(width * search_ratio))
    start = max(neighborhood + 1, center - radius)
    end = min(width - neighborhood - 1, center + radius)
    if start >= end:
        return center, 0.0

    scores = [0.0] * width
    for x in range(start, end):
        left_slice = column_mean[x - neighborhood : x]
        right_slice = column_mean[x + 1 : x + 1 + neighborhood]
        left_avg = sum(left_slice) / len(left_slice)
        right_avg = sum(right_slice) / len(right_slice)
        local_avg = 0.5 * (left_avg + right_avg)
        scores[x] = abs(column_mean[x] - local_avg)

    window_scores = scores[start:end]
    smooth = moving_average(window_scores, 7)
    best_local_idx = max(range(len(smooth)), key=lambda i: smooth[i]) if smooth else 0

    best_score = smooth[best_local_idx] if smooth else 0.0
    baseline = percentile(window_scores, 0.75) + 1e-6
    prominence = best_score / baseline if baseline > 0 else 0.0

    return start + best_local_idx, prominence


def is_likely_single_page(
    image: Image.Image,
    prominence: float,
    min_aspect_ratio: float,
    min_prominence: float,
) -> bool:
    width, height = image.size
    aspect_ratio = width / max(height, 1)
    return aspect_ratio < min_aspect_ratio or prominence < min_prominence


def split_spread(image: Image.Image, split_x: int, gutter: int = 0) -> tuple[Image.Image, Image.Image]:
    width, height = image.size
    split_x = max(1, min(width - 1, int(split_x)))
    gutter = max(0, int(gutter))

    left_end = max(1, split_x - gutter)
    right_start = min(width - 1, split_x + gutter)

    left = image.crop((0, 0, left_end, height))
    right = image.crop((right_start, 0, width, height))
    return left, right


def save_image(page: Image.Image, out_path: Path, suffix: str, jpeg_quality: int) -> None:
    if suffix in {".jpg", ".jpeg"}:
        page.save(out_path, format="JPEG", quality=jpeg_quality, subsampling=0, optimize=True)
    elif suffix in {".tif", ".tiff"}:
        page.save(out_path, format="TIFF", compression="tiff_lzw")
    else:
        page.save(out_path)


def detect_and_split(
    image: Image.Image,
    forced_split_x: int | None,
    gutter: int,
    rtl_order: bool,
    search_ratio: float,
    skip_single: bool,
    min_aspect_ratio: float,
    min_prominence: float,
) -> tuple[list[Image.Image], str]:
    split_x, prominence = find_fold_x(image, search_ratio=search_ratio)
    if forced_split_x is not None:
        split_x = forced_split_x

    if forced_split_x is None and skip_single and is_likely_single_page(
        image=image,
        prominence=prominence,
        min_aspect_ratio=min_aspect_ratio,
        min_prominence=min_prominence,
    ):
        return [image.copy()], f"single(prominence={prominence:.2f})"

    left, right = split_spread(image, split_x, gutter=gutter)
    pages = [right, left] if rtl_order else [left, right]
    return pages, f"split_x={split_x},prominence={prominence:.2f}"


def collect_images_grouped(inputs: Sequence[str]) -> dict[Path, list[Path]]:
    """Collect images recursively and group by their source parent folder."""

    groups: dict[Path, list[Path]] = defaultdict(list)

    for raw in inputs:
        p = Path(raw)
        if p.is_file():
            if p.suffix.lower() in SUPPORTED_EXTENSIONS:
                groups[p.parent].append(p)
            continue

        if p.is_dir():
            for child in sorted(p.rglob("*")):
                if child.is_file() and child.suffix.lower() in SUPPORTED_EXTENSIONS:
                    groups[child.parent].append(child)
            continue

        raise FileNotFoundError(f"Input not found: {p}")

    for folder in groups:
        groups[folder] = sorted(groups[folder])

    return groups


def output_subdir_for(source_folder: Path, roots: Sequence[Path], output_dir: Path) -> Path:
    """Map source folder to output folder, preserving nested structure."""

    for root in roots:
        try:
            rel = source_folder.relative_to(root)
            return output_dir / root.name / rel
        except ValueError:
            continue

    return output_dir / source_folder.name


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Split manga spreads (2 pages in 1 scan) into single pages.")
    parser.add_argument("inputs", nargs="+", help="Input image file(s) or directory(ies).")
    parser.add_argument(
        "-o",
        "--output-dir",
        default="",
        help="Subfolder name inside 'Tach anh' (default: put results directly in 'Tach anh').",
    )
    parser.add_argument("--split-x", type=int, default=None, help="Force split position X (pixels).")
    parser.add_argument("--gutter", type=int, default=0, help="Pixels to discard around fold on both sides.")
    parser.add_argument("--ltr", action="store_true", help="Export in left-to-right order (default is right-to-left).")
    parser.add_argument("--search-ratio", type=float, default=0.22, help="Center search range as a width fraction.")
    parser.add_argument(
        "--output-format",
        choices=["png", "jpg", "jpeg", "webp", "tif", "tiff", "bmp", "same"],
        default="png",
        help="Output format. Default: png (lossless). Use 'same' to keep input extension.",
    )
    parser.add_argument("--jpeg-quality", type=int, default=100, help="JPEG quality (1..100, default: 100).")
    parser.add_argument("--no-skip-single", action="store_true", help="Always split images, disable smart single-page detection.")
    parser.add_argument("--min-aspect-ratio", type=float, default=1.25, help="Aspect-ratio threshold for single-page detection.")
    parser.add_argument("--min-prominence", type=float, default=1.65, help="Fold-prominence threshold for spread detection.")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    output_dir = Path("Tach anh") / args.output_dir if args.output_dir else Path("Tach anh")
    rtl_order = not args.ltr
    input_roots = [Path(p) for p in args.inputs if Path(p).is_dir()]

    groups = collect_images_grouped(args.inputs)
    if not groups:
        print("No supported images found.")
        return

    for source_folder in sorted(groups):
        files = groups[source_folder]
        out_subdir = output_subdir_for(source_folder, input_roots, output_dir)
        out_subdir.mkdir(parents=True, exist_ok=True)

        page_counter = 1
        for file_path in files:
            with Image.open(file_path) as img:
                pages, info = detect_and_split(
                    image=img,
                    forced_split_x=args.split_x,
                    gutter=args.gutter,
                    rtl_order=rtl_order,
                    search_ratio=args.search_ratio,
                    skip_single=not args.no_skip_single,
                    min_aspect_ratio=args.min_aspect_ratio,
                    min_prominence=args.min_prominence,
                )

                if args.output_format == "same":
                    suffix = file_path.suffix.lower() or ".png"
                else:
                    suffix = f".{args.output_format}"

                for page in pages:
                    out_name = f"{page_counter:03d}{suffix}"
                    save_image(page, out_subdir / out_name, suffix, max(1, min(100, args.jpeg_quality)))
                    page_counter += 1

                print(f"{file_path} -> {info}, output_folder={out_subdir}")


if __name__ == "__main__":
    main()
