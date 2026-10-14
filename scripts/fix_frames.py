"""Remove the cheek mole from every pose and put a real up-left look in that slot."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision
from PIL import Image

ROOT = Path(r"C:\Users\jisto\Downloads\sportfolio")
FRAMES = ROOT / "public" / "frames"
NEW_UP_LEFT = Path(
    r"C:\Users\jisto\.cursor\projects\c-Users-jisto-Downloads-sportfolio\assets\character-up-left-fixed.jpg"
)

spec = importlib.util.spec_from_file_location("bf", ROOT / "scripts" / "build_frames.py")
bf = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bf)

detector = vision.FaceLandmarker.create_from_options(
    vision.FaceLandmarkerOptions(
        base_options=mp_python.BaseOptions(
            model_asset_path=str(ROOT / "scripts" / "face_landmarker.task")
        ),
        num_faces=1,
        min_face_detection_confidence=0.2,
    )
)

# Cheek points on both sides. The mark sits on the viewer's right cheek.
CHEEK = [352, 280, 425, 411, 347, 123, 50, 205, 187]


def landmarks(bgr: np.ndarray) -> np.ndarray:
    rgb = np.ascontiguousarray(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))
    result = detector.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb))
    if not result.face_landmarks:
        raise RuntimeError("no face")
    h, w = bgr.shape[:2]
    return np.array([(lm.x * w, lm.y * h) for lm in result.face_landmarks[0]], dtype=np.float32)


def remove_mole(bgr: np.ndarray, pts: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape
    mask = np.zeros((h, w), np.uint8)
    for idx in CHEEK:
        x, y = int(pts[idx][0]), int(pts[idx][1])
        r = 26
        x0, y0 = max(0, x - r), max(0, y - r)
        x1, y1 = min(w, x + r), min(h, y + r)
        patch = gray[y0:y1, x0:x1]
        if patch.size == 0:
            continue
        med = float(np.median(patch))
        dark = (patch < med - 42) & (patch < 110)
        local = np.zeros_like(gray)
        local[y0:y1, x0:x1] = dark.astype(np.uint8)
        count, labels, stats, _ = cv2.connectedComponentsWithStats(local, connectivity=8)
        for i in range(1, count):
            area = int(stats[i, cv2.CC_STAT_AREA])
            if 4 <= area <= 90:
                mask[labels == i] = 255
    if int(mask.sum()) == 0:
        return bgr
    mask = cv2.dilate(mask, np.ones((3, 3), np.uint8), iterations=1)
    return cv2.inpaint(bgr, mask, 4, cv2.INPAINT_TELEA)


def save_webp(bgr: np.ndarray, path: Path) -> None:
    Image.fromarray(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)).save(path, "WEBP", quality=86, method=4)


def pupil_offset(bgr: np.ndarray, pts: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape
    offs = []
    for a, b, top, bot in ((33, 133, 159, 145), (263, 362, 386, 374)):
        box = np.stack([pts[a], pts[b], pts[top], pts[bot]])
        x0, y0 = np.floor(box.min(0) - 2).astype(int)
        x1, y1 = np.ceil(box.max(0) + 2).astype(int)
        x0, y0 = max(0, x0), max(0, y0)
        x1, y1 = min(w - 1, x1), min(h - 1, y1)
        crop = gray[y0:y1, x0:x1]
        yy, xx = np.unravel_index(int(np.argmin(crop)), crop.shape)
        offs.append(((x0 + xx) - (x0 + x1) / 2, (y0 + yy) - (y0 + y1) / 2))
    return np.mean(offs, axis=0)


def load_webp(path: Path) -> np.ndarray:
    rgb = np.array(Image.open(path).convert("RGB"))
    return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)


def main() -> None:
    center = load_webp(FRAMES / "center.webp")
    bg = bf.corner_color(center)
    anchor = bf.torso_point(center)

    frames = [load_webp(FRAMES / f"{i:03d}.webp") for i in range(8)]
    cleaned = []
    for i, img in enumerate(frames):
        pts = landmarks(img)
        out = remove_mole(img, pts)
        cleaned.append(out)
        print(f"cleaned {i:03d}")

    fresh = bf.load_bgr(NEW_UP_LEFT)
    fresh = bf.flatten_red(bf.remove_cursor(fresh, bg), bg)
    fresh = bf.align_torso(fresh, anchor, bg)
    fresh = bf.flatten_red(fresh, bg)
    fresh_pts = landmarks(fresh)
    fresh = remove_mole(fresh, fresh_pts)
    print("new up-left pupil", np.round(pupil_offset(fresh, fresh_pts), 1))

    # Slot 4 is straight left. The old file looks right, so use the real left pose.
    # Slot 5 is up-left on screen.
    cleaned[4] = cleaned[3]
    cleaned[5] = fresh

    center_pts = landmarks(center)
    center = remove_mole(center, center_pts)

    for i, img in enumerate(cleaned):
        save_webp(img, FRAMES / f"{i:03d}.webp")
    save_webp(center, FRAMES / "center.webp")

    meta_path = FRAMES / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["version"] = 4
    meta["order"][4] = "left"
    meta["order"][5] = "up-left"
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")

    # Cheek close-up so we can see the mark is gone.
    y, x = 376, 793
    crop = cv2.cvtColor(center, cv2.COLOR_BGR2RGB)[y - 40 : y + 40, x - 40 : x + 40]
    Image.fromarray(crop).resize((240, 240), Image.Resampling.NEAREST).save(ROOT / "scripts" / "mole-after.png")
    eye = cv2.cvtColor(fresh, cv2.COLOR_BGR2RGB)[200:460, 430:860]
    Image.fromarray(eye).save(ROOT / "scripts" / "up-left-eye.jpg", quality=92)
    print("version", meta["version"])


if __name__ == "__main__":
    main()
