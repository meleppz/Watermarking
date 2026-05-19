"""
dct_watermark.py — Stronger watermarking using DCT-domain spread-spectrum + repetition

This module provides:
- generate_binary_watermark
- embed_watermark_dct
- extract_watermark_dct
- jpeg_compress
- calculate_ber, calculate_nc, calculate_psnr

Design notes:
- Operates on Y channel (YCbCr), 8x8 DCT blocks (scipy dct)
- Embeds each payload bit into multiple blocks (repetition) and multiple mid-band
  coefficients via a pseudo-random sequence (seed key).
- Uses additive spread-spectrum (alpha scaled) rather than tiny quant shifts.
"""

import io
import numpy as np
from PIL import Image
from scipy.fftpack import dct, idct


# --- helpers: block DCT/IDCT (8x8) ---------------------------------
def block_dct(block: np.ndarray) -> np.ndarray:
    return dct(dct(block.T, norm="ortho").T, norm="ortho")


def block_idct(block: np.ndarray) -> np.ndarray:
    return idct(idct(block.T, norm="ortho").T, norm="ortho")


# --- watermark generation -------------------------------------------
def generate_binary_watermark(size=(32, 32), seed: int = 42) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return rng.integers(0, 2, size=size, dtype=np.uint8)


# mid-band coefficient positions (u,v) inside 8x8 block (typical stable set)
MID_BAND_POS = [(1, 2), (2, 1), (3, 0), (0, 3), (2, 2), (1, 3), (3, 1), (4, 0), (0, 4)]


def _get_blocks(Y: np.ndarray):
    H, W = Y.shape
    bh = H // 8
    bw = W // 8
    for by in range(bh):
        for bx in range(bw):
            y0 = by * 8
            x0 = bx * 8
            yield by, bx, Y[y0:y0+8, x0:x0+8]


def jpeg_compress(image_array: np.ndarray, quality: int) -> np.ndarray:
    img_pil = Image.fromarray(image_array.astype(np.uint8))
    buffer = io.BytesIO()
    img_pil.save(buffer, format="JPEG", quality=quality)
    buffer.seek(0)
    return np.array(Image.open(buffer).convert("RGB"))


# --- embed/extract using additive spread-spectrum + repetition --------
def embed_watermark_dct(image_array: np.ndarray,
                        watermark: np.ndarray,
                        seed: int = 42,
                        alpha: float = 4.0,
                        repeats: int = 5,
                        k_per_bit: int = 8) -> np.ndarray:
    """
    Embed watermark into Y channel using DCT additive spread-spectrum.
    - alpha controls strength (higher -> more robust but more visible)
    - repeats: how many separate blocks encode each bit (repetition)
    - k_per_bit: how many distinct mid-band coeffs per selected block to use
    """
    img = Image.fromarray(image_array.astype(np.uint8))
    ycbcr = np.array(img.convert("YCbCr"), dtype=float)
    Y = ycbcr[:, :, 0]

    H, W = Y.shape
    if H % 8 != 0 or W % 8 != 0:
        raise ValueError("Image dimensions must be multiples of 8")

    payload = watermark.flatten()
    payload_len = payload.size

    # prepare PR selection
    rng = np.random.default_rng(seed)
    total_blocks = (H // 8) * (W // 8)
    block_indices = np.arange(total_blocks)
    rng.shuffle(block_indices)

    # convert Y into DCT domain blocks, modify in-place into copy
    Y_out = Y.copy()

    bi = 0
    # for each payload bit, embed it in 'repeats' different blocks
    for p in payload:
        for r in range(repeats):
            if bi >= total_blocks:
                # ran out of blocks (shouldn't happen for reasonable params)
                break
            bidx = block_indices[bi]
            by = bidx // (W // 8)
            bx = bidx % (W // 8)
            y0 = by * 8
            x0 = bx * 8
            block = Y_out[y0:y0+8, x0:x0+8]
            B = block_dct(block)

            # select k_per_bit positions (rotate through MID_BAND_POS)
            for k in range(k_per_bit):
                pos = MID_BAND_POS[k % len(MID_BAND_POS)]
                u, v = pos
                # add signed pseudorandom small sequence scaled by alpha
                sign = 1.0 if p == 1 else -1.0
                # use RNG seeded per block for reproducibility
                val = alpha * (0.8 + 0.4 * (rng.random()))
                B[u, v] = B[u, v] + sign * val

            # inverse DCT back
            Y_out[y0:y0+8, x0:x0+8] = block_idct(B)
            bi += 1

    # reconstruct image
    ycbcr[:, :, 0] = np.clip(Y_out, 0, 255)
    rgb_out = Image.fromarray(ycbcr.astype(np.uint8), mode='YCbCr').convert('RGB')
    return np.array(rgb_out)


def extract_watermark_dct(image_array: np.ndarray,
                          wm_shape: tuple = (32, 32),
                          seed: int = 42,
                          repeats: int = 5,
                          k_per_bit: int = 8) -> np.ndarray:
    """
    Extract watermark previously embedded with embed_watermark_dct.
    Uses same seed, repeats, and k_per_bit to retrieve bits with voting.
    """
    img = Image.fromarray(image_array.astype(np.uint8))
    ycbcr = np.array(img.convert("YCbCr"), dtype=float)
    Y = ycbcr[:, :, 0]

    H, W = Y.shape
    total_blocks = (H // 8) * (W // 8)

    # allow wm_shape to be int (number of bits) or tuple
    if isinstance(wm_shape, (tuple, list)):
        payload_len = int(np.prod(wm_shape))
    else:
        payload_len = int(wm_shape)

    rng = np.random.default_rng(seed)
    block_indices = np.arange(total_blocks)
    rng.shuffle(block_indices)

    bits_extracted = []
    bi = 0
    for i in range(payload_len):
        votes = []
        for r in range(repeats):
            if bi >= total_blocks:
                break
            bidx = block_indices[bi]
            by = bidx // (W // 8)
            bx = bidx % (W // 8)
            y0 = by * 8
            x0 = bx * 8
            block = Y[y0:y0+8, x0:x0+8]
            B = block_dct(block)

            # correlate sign over k_per_bit positions
            s = 0.0
            for k in range(k_per_bit):
                pos = MID_BAND_POS[k % len(MID_BAND_POS)]
                u, v = pos
                s += B[u, v]

            # positive average indicates bit 1
            votes.append(1 if s > 0 else 0)
            bi += 1

        # majority vote across repeats
        votes = np.array(votes, dtype=np.int32)
        bit = 1 if votes.sum() > (len(votes) / 2) else 0
        bits_extracted.append(bit)

    arr = np.array(bits_extracted, dtype=np.uint8)
    if isinstance(wm_shape, (tuple, list)):
        return arr.reshape(wm_shape)
    else:
        return arr.reshape((payload_len,))


# --- metrics --------------------------------------------------------
def calculate_ber(original_wm: np.ndarray, extracted_wm: np.ndarray) -> float:
    return float(np.mean(original_wm.flatten() != extracted_wm.flatten()))


def calculate_nc(original_wm: np.ndarray, extracted_wm: np.ndarray) -> float:
    orig = original_wm.flatten().astype(float)
    extr = extracted_wm.flatten().astype(float)
    denom = np.sqrt(np.dot(orig, orig)) * np.sqrt(np.dot(extr, extr))
    if denom < 1e-10:
        return 0.0
    return float(np.dot(orig, extr) / denom)


def calculate_psnr(img_a: np.ndarray, img_b: np.ndarray) -> float:
    mse = np.mean((img_a.astype(float) - img_b.astype(float)) ** 2)
    if mse == 0:
        return float('inf')
    return float(10 * np.log10(255.0 ** 2 / mse))