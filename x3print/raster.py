import numpy as np
from PIL import Image, ImageOps

HEAD = 864
DOTS_PER_MM = 300 / 25.4


def load(path, width=HEAD, rotate=0, nearest=False):
    im = ImageOps.exif_transpose(Image.open(path)).convert("L")
    if rotate:
        im = im.rotate(-rotate, expand=True)
    h = max(1, round(im.height * width / im.width))
    im = im.resize((width, h), Image.NEAREST if nearest else Image.LANCZOS)
    return np.asarray(im, dtype=np.float32) / 255.0


def adjust(a, brightness=0.0, contrast=0.0, gamma=1.0, invert=False):
    a = (a - 0.5) * (1.0 + contrast) + 0.5 + brightness
    a = np.clip(a, 0.0, 1.0) ** (1.0 / gamma)
    return 1.0 - a if invert else a


_BAYER8 = np.array([
    [0, 32, 8, 40, 2, 34, 10, 42], [48, 16, 56, 24, 50, 18, 58, 26],
    [12, 44, 4, 36, 14, 46, 6, 38], [60, 28, 52, 20, 62, 30, 54, 22],
    [3, 35, 11, 43, 1, 33, 9, 41], [51, 19, 59, 27, 49, 17, 57, 25],
    [15, 47, 7, 39, 13, 45, 5, 37], [63, 31, 55, 23, 61, 29, 53, 21]], np.float32)
_CLUSTER8 = np.array([
    [24, 10, 12, 26, 35, 47, 49, 37], [8, 0, 2, 14, 45, 59, 61, 51],
    [22, 6, 4, 16, 43, 57, 63, 53], [30, 20, 18, 28, 33, 41, 55, 39],
    [34, 46, 48, 36, 25, 11, 13, 27], [44, 58, 60, 50, 9, 1, 3, 15],
    [42, 56, 62, 52, 23, 7, 5, 17], [32, 40, 54, 38, 31, 21, 19, 29]], np.float32)

_KERNELS = {
    "floyd": [(1, 0, 7 / 16), (-1, 1, 3 / 16), (0, 1, 5 / 16), (1, 1, 1 / 16)],
    "atkinson": [(1, 0, 1 / 8), (2, 0, 1 / 8), (-1, 1, 1 / 8), (0, 1, 1 / 8), (1, 1, 1 / 8), (0, 2, 1 / 8)],
}

_BAYER2 = np.array([[0, 2], [3, 1]], np.float32)
_BAYER4 = np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]], np.float32)
_CLUSTER4 = np.array([[12, 5, 6, 13], [4, 0, 1, 7], [11, 3, 2, 8], [15, 10, 9, 14]], np.float32)
_ORDERED = {"bayer2": _BAYER2, "bayer4": _BAYER4, "bayer8": _BAYER8, "cluster4": _CLUSTER4, "cluster8": _CLUSTER8}

MODES = ("bayer2", "bayer4", "bayer8", "cluster4", "cluster8", "floyd", "atkinson", "threshold")


def dither(a, mode="floyd", threshold=0.5):
    h, w = a.shape
    if mode == "threshold":
        return (a < threshold).astype(np.uint8)
    if mode in _ORDERED:
        m = _ORDERED[mode]
        n = m.shape[0]
        t = (np.tile(m, (h // n + 1, w // n + 1))[:h, :w] + 0.5) / (n * n)
        return (a < t).astype(np.uint8)
    k = _KERNELS[mode]
    e = a.astype(np.float32).copy()
    out = np.zeros((h, w), np.uint8)
    for y in range(h):
        row = e[y]
        for x in range(w):
            old = row[x]
            new = 0.0 if old < threshold else 1.0
            out[y, x] = new == 0.0
            err = old - new
            for dx, dy, f in k:
                xx, yy = x + dx, y + dy
                if 0 <= xx < w and yy < h:
                    e[yy, xx] += err * f
    return out


def pad_to_head(bits, align="center"):
    h, w = bits.shape
    if w >= HEAD:
        return bits[:, :HEAD]
    left = {"left": 0, "right": HEAD - w}.get(align, (HEAD - w) // 2)
    out = np.zeros((h, HEAD), np.uint8)
    out[:, left:left + w] = bits
    return out


def pack(bits):
    return np.packbits(bits.astype(np.uint8), axis=1).tobytes()
