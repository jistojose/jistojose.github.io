"""Pre-extract cursor-tracking WebP frames from directional portraits.

Runtime never seeks a video. Each compass direction is one crisp still, shifted
so the torso matches the center portrait. The page draws exactly one frame.
"""

from __future__ import annotations

import json
import urllib.request
from pathlib import Path

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
ASSET_DIR = Path(
    r"C:\Users\jisto\.cursor\projects\c-Users-jisto-Downloads-sportfolio\assets"
)
OUT_DIR = ROOT / "public" / "frames"
MODEL_PATH = ROOT / "scripts" / "face_landmarker.task"
MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/face_landmarker/"
    "face_landmarker/float16/1/face_landmarker.task"
)

# Clockwise from screen-right. Some generated stills were named from the
# character's own left/right, so the upper diagonals are paired to the
# direction a viewer sees.
ORDER = [
    "right",
    "down-right",
    "down",
    "down-left",
    "left",
    "up-right",
    "up",
    "up-left",
]

FRAME_COUNT = 8
OUT_W, OUT_H = 1280, 720


def download_model() -> None:
    if MODEL_PATH.exists() and MODEL_PATH.stat().st_size > 1000:
        return
    urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)


def load_bgr(path: Path) -> np.ndarray:
    img = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if img is None:
        raise FileNotFoundError(path)
    return cv2.resize(img, (OUT_W, OUT_H), interpolation=cv2.INTER_AREA)


def corner_color(img: np.ndarray) -> tuple[int, int, int]:
    patch = img[8:28, 8:28].reshape(-1, 3)
    med = np.median(patch, axis=0).astype(np.uint8)
    return int(med[0]), int(med[1]), int(med[2])


def remove_cursor(img: np.ndarray, bg: tuple[int, int, int]) -> np.ndarray:
    b, g, r = cv2.split(img)
    white = ((r > 235) & (g > 235) & (b > 235)).astype(np.uint8)
    if int(white.sum()) < 20:
        return img
    white = cv2.dilate(white, np.ones((15, 15), np.uint8))
    out = img.copy()
    out[white > 0] = bg
    return out


def flatten_red(img: np.ndarray, color: tuple[int, int, int]) -> np.ndarray:
    """Recolor only the solid backdrop. Thin red shadows on the face stay put."""
    b, g, r = cv2.split(img)
    pure = ((r > 175) & (g < 50) & (b < 50)).astype(np.float32)
    density = cv2.blur(pure, (11, 11))
    out = img.copy()
    out[density > 0.82] = color
    return out


def torso_point(img: np.ndarray) -> np.ndarray:
    b, g, r = cv2.split(img)
    person = ~((r > 175) & (g < 50) & (b < 50))
    h = img.shape[0]
    ys, xs = np.where(person)
    sel = ys > int(h * 0.82)
    if int(sel.sum()) < 50:
        sel = ys > int(h * 0.7)
    return np.array([xs[sel].mean(), ys[sel].mean()], dtype=np.float32)


def align_torso(img: np.ndarray, anchor: np.ndarray, bg: tuple[int, int, int]) -> np.ndarray:
    delta = anchor - torso_point(img)
    matrix = np.float32([[1, 0, float(delta[0])], [0, 1, float(delta[1])]])
    return cv2.warpAffine(
        img,
        matrix,
        (OUT_W, OUT_H),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=bg,
    )


def save_webp(img: np.ndarray, path: Path) -> None:
    rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    Image.fromarray(rgb).save(path, "WEBP", quality=84, method=4)


def bgr_hex(color: tuple[int, int, int]) -> str:
    b, g, r = color
    return f"#{r:02x}{g:02x}{b:02x}"


def main() -> None:
    download_model()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    detector = vision.FaceLandmarker.create_from_options(
        vision.FaceLandmarkerOptions(
            base_options=mp_python.BaseOptions(model_asset_path=str(MODEL_PATH)),
            num_faces=1,
            min_face_detection_confidence=0.2,
        )
    )

    center = load_bgr(ASSET_DIR / "character-center.jpg")
    bg = corner_color(center)
    center = flatten_red(remove_cursor(center, bg), bg)
    anchor = torso_point(center)
    print("bg", bgr_hex(bg))

    keys = []
    for name in ORDER:
        img = load_bgr(ASSET_DIR / f"character-{name}.jpg")
        img = flatten_red(remove_cursor(img, bg), bg)
        img = align_torso(img, anchor, bg)
        img = flatten_red(img, bg)
        keys.append(img)
        print("key", name)

    for i, frame in enumerate(keys):
        save_webp(frame, OUT_DIR / f"{i:03d}.webp")
        print(f"frame {i:03d} {ORDER[i]}")

    # Drop any older high-index frames from a previous 64-frame build.
    for stale in OUT_DIR.glob("*.webp"):
        if stale.stem.isdigit() and int(stale.stem) >= len(keys):
            stale.unlink()

    save_webp(center, OUT_DIR / "center.webp")

    rgb = np.ascontiguousarray(cv2.cvtColor(center, cv2.COLOR_BGR2RGB))
    result = detector.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb))
    lm = result.face_landmarks[0]
    eye = (
        (lm[33].x + lm[263].x) * 0.5,
        (lm[33].y + lm[263].y) * 0.5,
    )
    meta = {
        "version": 3,
        "frameCount": FRAME_COUNT,
        "bg": bgr_hex(bg),
        "width": OUT_W,
        "height": OUT_H,
        "face": {"x": float(eye[0]), "y": float(eye[1])},
        "order": ORDER,
    }
    (OUT_DIR / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

    cells = []
    labeled = [("center", center)] + list(zip(ORDER, keys))
    for label, im in labeled:
        cell = cv2.resize(im, (320, 180))
        cv2.putText(cell, label, (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2, cv2.LINE_AA)
        cells.append(cell)
    cols = 5
    rows = []
    for start in range(0, len(cells), cols):
        chunk = cells[start : start + cols]
        if len(chunk) < cols:
            chunk += [np.zeros_like(chunk[0])] * (cols - len(chunk))
        rows.append(cv2.hconcat(chunk))
    preview = ROOT / "scripts" / "preview-sheet.jpg"
    cv2.imwrite(str(preview), cv2.vconcat(rows), [int(cv2.IMWRITE_JPEG_QUALITY), 90])
    print("wrote", preview)


if __name__ == "__main__":
    main()
