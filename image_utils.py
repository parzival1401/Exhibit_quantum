"""
image_utils.py — Shared Image Processing Utilities

  create_gradient_palette  → 2-D HSV spectrum for Window 3
  apply_color_to_template  → paint all 'white' regions with a target color
  quantum_collapse         → Normal-distribution weighted color sampler
  find_test_image          → Scans the repo for a paint-by-numbers template
"""

import os
import glob
import numpy as np
import cv2


# ─────────────────────────────────────────────────────────────────────────────
# Gradient palette
# ─────────────────────────────────────────────────────────────────────────────

def create_gradient_palette(width: int = 512, height: int = 300) -> np.ndarray:
    """
    Returns an (height × width × 3) uint8 RGB array.

    Layout:
      X-axis  →  Hue 0 → 360°  (full rainbow)
      Y-axis  ↓  Value 255 → 20  (bright at top, near-black at bottom)
      Saturation is fixed at 220 (slightly desaturated for a softer look)
    """
    H = np.tile(
        np.linspace(0, 179, width, dtype=np.uint8),
        (height, 1)
    )
    S = np.full((height, width), 220, dtype=np.uint8)
    V = np.tile(
        np.linspace(255, 20, height, dtype=np.uint8)[:, np.newaxis],
        (1, width)
    )
    hsv = np.stack([H, S, V], axis=2)
    return cv2.cvtColor(hsv, cv2.COLOR_HSV2RGB)


# ─────────────────────────────────────────────────────────────────────────────
# Template color fill
# ─────────────────────────────────────────────────────────────────────────────

def apply_color_to_template(
    template_array: np.ndarray,
    color: tuple,
    fill_threshold: int = 180,
    outline_threshold: int = 80
) -> np.ndarray:
    """
    Returns a copy of template_array where every 'light' (fillable) pixel
    is replaced with *color*, and every 'dark' (outline) pixel is kept as-is.

    Pixels with perceptual luminance > fill_threshold  → filled with color
    Pixels with perceptual luminance < outline_threshold → kept black
    Pixels in between                                   → blended proportionally

    Args:
        template_array : H×W×3 uint8 RGB numpy array
        color          : (R, G, B) target fill color
        fill_threshold : luminance above which a pixel is considered 'white'
        outline_threshold : luminance below which a pixel is 'outline'
    """
    r_ch = template_array[:, :, 0].astype(np.float32)
    g_ch = template_array[:, :, 1].astype(np.float32)
    b_ch = template_array[:, :, 2].astype(np.float32)

    lum = 0.299 * r_ch + 0.587 * g_ch + 0.114 * b_ch  # perceptual luminance

    fill_mask    = lum >= fill_threshold
    outline_mask = lum <= outline_threshold
    blend_mask   = ~fill_mask & ~outline_mask

    result = template_array.copy()

    # Solid fill
    result[fill_mask, 0] = color[0]
    result[fill_mask, 1] = color[1]
    result[fill_mask, 2] = color[2]

    # Smooth anti-aliased transition
    if blend_mask.any():
        t = ((lum[blend_mask] - outline_threshold) /
             (fill_threshold - outline_threshold))
        result[blend_mask, 0] = np.clip(
            t * color[0] + (1 - t) * result[blend_mask, 0], 0, 255
        ).astype(np.uint8)
        result[blend_mask, 1] = np.clip(
            t * color[1] + (1 - t) * result[blend_mask, 1], 0, 255
        ).astype(np.uint8)
        result[blend_mask, 2] = np.clip(
            t * color[2] + (1 - t) * result[blend_mask, 2], 0, 255
        ).astype(np.uint8)

    return result


# ─────────────────────────────────────────────────────────────────────────────
# Quantum collapse engine
# ─────────────────────────────────────────────────────────────────────────────

def quantum_collapse(
    gradient_array: np.ndarray,
    sq_x: int,
    sq_y: int,
    sq_size: int
) -> tuple:
    """
    The 'Quantum Measurement' step.

    1. Extract every pixel inside the selector square.
    2. Model each channel independently as a Normal distribution:
           μ  = channel mean across the selection
           σ  = channel std-dev (minimum clamped to 1)
    3. Compute probability P(pixel) = ∏ₖ  N(pixel_k ; μ_k, σ_k)
       (joint probability under the factored Gaussian).
    4. Normalise → probability weights.
    5. Weighted random sample → one pixel = the 'collapsed' color.

    Returns (R, G, B) as a tuple of ints.
    """
    h, w = gradient_array.shape[:2]
    half  = sq_size // 2

    x1 = max(0, sq_x - half)
    y1 = max(0, sq_y - half)
    x2 = min(w, sq_x + half)
    y2 = min(h, sq_y + half)

    region = gradient_array[y1:y2, x1:x2]

    if region.size == 0:
        return (128, 128, 128)

    pixels = region.reshape(-1, 3).astype(np.float64)

    if len(pixels) == 0:
        return (128, 128, 128)

    means = np.mean(pixels, axis=0)          # shape (3,)
    stds  = np.std(pixels, axis=0)
    stds  = np.maximum(stds, 1.0)            # prevent division-by-zero

    def _normal_pdf(x: np.ndarray, mu: float, sigma: float) -> np.ndarray:
        """Unnormalised Gaussian PDF (normalisation factor cancels in ratio)."""
        return np.exp(-0.5 * ((x - mu) / sigma) ** 2)

    probs = (
        _normal_pdf(pixels[:, 0], means[0], stds[0]) *
        _normal_pdf(pixels[:, 1], means[1], stds[1]) *
        _normal_pdf(pixels[:, 2], means[2], stds[2])
    )

    total = probs.sum()
    if total > 0:
        probs /= total
    else:
        probs = np.ones(len(pixels)) / len(pixels)

    idx = np.random.choice(len(pixels), p=probs)
    return tuple(int(v) for v in pixels[idx])


# ─────────────────────────────────────────────────────────────────────────────
# Region detection  (connected-component labelling)
# ─────────────────────────────────────────────────────────────────────────────

def identify_regions(template_array: np.ndarray) -> tuple:
    """
    Detect distinct fillable regions via connected components.

    Any pixel with perceptual luminance > 80 is considered 'fillable' (white /
    light-coloured area).  The complementary dark pixels are outlines (region 0).

    Returns
    -------
    num_labels : int   — total number of labels (including 0 = outline)
    labels     : H×W int32 ndarray — each pixel's region ID (0 = outline)
    """
    r = template_array[:, :, 0].astype(np.float32)
    g = template_array[:, :, 1].astype(np.float32)
    b = template_array[:, :, 2].astype(np.float32)
    lum = 0.299 * r + 0.587 * g + 0.114 * b

    fillable = (lum > 80).astype(np.uint8) * 255
    num_labels, labels = cv2.connectedComponents(fillable, connectivity=4)

    # Force outline pixels back to region 0
    labels[lum <= 80] = 0

    return num_labels, labels.astype(np.int32)


def apply_region_colors(
    template_array: np.ndarray,
    region_labels: np.ndarray,
    region_colors: dict,
    selected_region: int = -1,
    default_fill: tuple = (225, 225, 225),
) -> np.ndarray:
    """
    Render the template with per-region colours.

    Parameters
    ----------
    template_array  : H×W×3 uint8 RGB  — the original line-art image
    region_labels   : H×W int32        — 0 = outline, >0 = region ID
    region_colors   : {region_id: (R,G,B)} — explicitly painted regions
    selected_region : highlight this region ID with a yellow tint (-1 = none)
    default_fill    : colour for regions not yet assigned a colour
    """
    result = template_array.copy().astype(np.float32)

    # Paint all non-outline pixels with the default (uncoloured) fill
    fillable = region_labels > 0
    result[fillable] = default_fill

    # Apply explicit per-region colours
    for rid, color in region_colors.items():
        mask = region_labels == rid
        result[mask] = color

    # Yellow highlight for the currently selected region
    if selected_region > 0:
        sel = region_labels == selected_region
        if sel.any():
            yellow = np.array([255.0, 215.0, 40.0])
            result[sel] = 0.55 * result[sel] + 0.45 * yellow

    return np.clip(result, 0, 255).astype(np.uint8)


# ─────────────────────────────────────────────────────────────────────────────
# Test image finder
# ─────────────────────────────────────────────────────────────────────────────

def find_test_image(directory: str = '.') -> str | None:
    """
    Recursively scans *directory* for a template image using two passes:

    Pass 1 — Priority names: any file whose name contains 'test' or 'crayo'
             (SVG checked first so vector art takes priority over raster copies).
    Pass 2 — Fallback: the first image of any name found in the directory
             (allows dropping any image into the folder without renaming it).

    Returns the absolute path of the first match, or None if the folder is empty.
    """
    EXTENSIONS   = ('svg', 'png', 'jpg', 'jpeg', 'bmp')
    PRIORITY_KEYS = ('test', 'crayo')

    # Pass 1: priority filenames
    for ext in EXTENSIONS:
        for path in glob.glob(
            os.path.join(directory, f'**/*.{ext}'), recursive=True
        ):
            name = os.path.basename(path).lower()
            if any(key in name for key in PRIORITY_KEYS):
                return path

    # Pass 2: any image in the folder
    for ext in EXTENSIONS:
        matches = glob.glob(
            os.path.join(directory, f'**/*.{ext}'), recursive=True
        )
        if matches:
            return matches[0]

    return None
