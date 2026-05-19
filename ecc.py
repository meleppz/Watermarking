"""
ecc.py 	6 Simple Hamming(7,4) encoder/decoder utilities for bit arrays

Functions:
- hamming74_encode(bits, original_length=None) -> encoded_bits, pad_len
- hamming74_decode(encoded_bits, pad_len) -> decoded_bits, num_corrected

Notes: bits are numpy arrays of 0/1 uint8 or Python lists.
"""
import numpy as np


def hamming74_encode(bits):
    """Encode a 1D bit array using Hamming(7,4).
    Returns encoded_bits (1D numpy uint8) and pad_len (number of padding bits added to make multiple of 4).
    """
    b = np.asarray(bits, dtype=np.uint8).flatten()
    pad_len = (-len(b)) % 4
    if pad_len:
        b = np.concatenate([b, np.zeros(pad_len, dtype=np.uint8)])

    # group into 4-bit blocks
    b4 = b.reshape(-1, 4)
    encoded = []
    for d in b4:
        d1, d2, d3, d4 = int(d[0]), int(d[1]), int(d[2]), int(d[3])
        # parity bits
        p1 = (d1 ^ d2 ^ d4) & 1
        p2 = (d1 ^ d3 ^ d4) & 1
        p3 = (d2 ^ d3 ^ d4) & 1
        # codeword: p1 p2 d1 p3 d2 d3 d4
        code = [p1, p2, d1, p3, d2, d3, d4]
        encoded.extend(code)

    return np.array(encoded, dtype=np.uint8), pad_len


def hamming74_decode(encoded_bits, pad_len=0):
    """Decode Hamming(7,4) encoded bits. Returns decoded_bits (trimmed to original length) and num_corrected.
    encoded_bits: 1D array of length multiple of 7.
    pad_len: number of padding bits that were added during encoding (0-3).
    """
    eb = np.asarray(encoded_bits, dtype=np.uint8).flatten()
    if len(eb) % 7 != 0:
        raise ValueError('Encoded bits length must be multiple of 7')

    blocks = eb.reshape(-1, 7)
    decoded = []
    num_corrected = 0
    for cw in blocks:
        c = [int(x) for x in cw]
        # syndrome bits
        s1 = c[0] ^ c[2] ^ c[4] ^ c[6]
        s2 = c[1] ^ c[2] ^ c[5] ^ c[6]
        s3 = c[3] ^ c[4] ^ c[5] ^ c[6]
        syndrome = (s3 << 2) | (s2 << 1) | s1
        if syndrome != 0:
            # flip bit at position syndrome (1-based)
            pos = syndrome - 1
            if 0 <= pos < 7:
                c[pos] ^= 1
                num_corrected += 1

        # extract data bits d1,d2,d3,d4 at positions 3,5,6,7 (0-based 2,4,5,6)
        d1 = c[2]; d2 = c[4]; d3 = c[5]; d4 = c[6]
        decoded.extend([d1, d2, d3, d4])

    # remove padding
    if pad_len:
        decoded = decoded[:-pad_len]

    return np.array(decoded, dtype=np.uint8), num_corrected

