"""
generate_test_image.py — Paint-by-Numbers Template Generator

Produces  test_pattern.png — a mandala-style line-art template with:
  • Outer decorative border
  • 4 corner ornaments (X-crossed squares)
  • 4 background quadrant strips (between border and circle)
  • Outer ring   → 8 arc segments  (separated by radial spokes)
  • Middle ring  → 8 arc segments  (offset 22.5° from outer spokes)
  • Inner circle → 4 quadrants
  • Center dot

All region interiors are pure white (255,255,255).
All outlines   are pure black  (0,0,0).
This guarantees a clean luminance-threshold mask in image_utils.py.

Run directly:
    python generate_test_image.py
Or import create_test_image() for programmatic use.
"""

import math
import os
from PIL import Image, ImageDraw


def create_test_image(
    width: int = 600,
    height: int = 600,
    filename: str = 'test_pattern.png'
) -> str:
    """
    Draw and save the paint-by-numbers template.
    Returns the absolute path to the saved file.
    """
    img  = Image.new('RGB', (width, height), (255, 255, 255))
    draw = ImageDraw.Draw(img)

    BLACK = (0, 0, 0)
    WHITE = (255, 255, 255)
    LW    = 3          # line width (pixels)

    cx, cy = width // 2, height // 2

    # ── Outer border ────────────────────────────────────────────────────────
    draw.rectangle([4, 4, width - 4, height - 4], outline=BLACK, width=LW)

    # ── 4 Corner ornaments (squares with diagonal X) ─────────────────────
    SQ      = 72
    MARGIN  = 18
    corners = [
        (MARGIN,              MARGIN),
        (width - MARGIN - SQ, MARGIN),
        (MARGIN,              height - MARGIN - SQ),
        (width - MARGIN - SQ, height - MARGIN - SQ),
    ]
    for (x0, y0) in corners:
        x1, y1 = x0 + SQ, y0 + SQ
        draw.rectangle([x0, y0, x1, y1], outline=BLACK, fill=WHITE, width=LW)
        draw.line([(x0, y0), (x1, y1)], fill=BLACK, width=LW)
        draw.line([(x0, y1), (x1, y0)], fill=BLACK, width=LW)

    # ── Main (outer) circle ──────────────────────────────────────────────
    R = min(cx, cy) - 44
    draw.ellipse(
        [cx - R, cy - R, cx + R, cy + R],
        outline=BLACK, fill=WHITE, width=LW
    )

    # ── Middle circle (ring divider) ─────────────────────────────────────
    R2 = int(R * 0.57)
    draw.ellipse(
        [cx - R2, cy - R2, cx + R2, cy + R2],
        outline=BLACK, fill=WHITE, width=LW
    )

    # ── Inner / center circle ────────────────────────────────────────────
    R3 = int(R * 0.22)
    draw.ellipse(
        [cx - R3, cy - R3, cx + R3, cy + R3],
        outline=BLACK, fill=WHITE, width=LW
    )

    # ── 8 spokes in the outer ring  (R2 → R) ────────────────────────────
    for i in range(8):
        angle = math.radians(i * 45)
        draw.line([
            (cx + R2 * math.cos(angle), cy + R2 * math.sin(angle)),
            (cx + R  * math.cos(angle), cy + R  * math.sin(angle)),
        ], fill=BLACK, width=LW)

    # ── 8 spokes in the middle ring (R3 → R2, offset 22.5°) ─────────────
    for i in range(8):
        angle = math.radians(i * 45 + 22.5)
        draw.line([
            (cx + R3 * math.cos(angle), cy + R3 * math.sin(angle)),
            (cx + R2 * math.cos(angle), cy + R2 * math.sin(angle)),
        ], fill=BLACK, width=LW)

    # ── 4 cardinal spokes inside inner circle (0 → R3) ──────────────────
    for angle_deg in (0, 90, 180, 270):
        angle = math.radians(angle_deg)
        draw.line([
            (cx, cy),
            (cx + R3 * math.cos(angle), cy + R3 * math.sin(angle)),
        ], fill=BLACK, width=LW)

    # ── Axis lines: circle edge → border (creates background quadrants) ──
    draw.line([(cx, cy - R), (cx, 4 + LW)],            fill=BLACK, width=LW)
    draw.line([(cx, cy + R), (cx, height - 4 - LW)],   fill=BLACK, width=LW)
    draw.line([(cx - R, cy), (4 + LW, cy)],            fill=BLACK, width=LW)
    draw.line([(cx + R, cy), (width - 4 - LW, cy)],    fill=BLACK, width=LW)

    # ── Save ─────────────────────────────────────────────────────────────
    out_path = os.path.abspath(filename)
    img.save(out_path)
    print(f"[generate_test_image] Template saved → {out_path}")
    return out_path


if __name__ == '__main__':
    create_test_image()
