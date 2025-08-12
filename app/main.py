from io import BytesIO
from typing import List, Optional, Tuple
from pathlib import Path
from datetime import datetime
import re

import numpy as np
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image
import cv2

from insightface.app import FaceAnalysis

from .storage import FaceStorage


app = FastAPI(title="Face Recognition App", version="1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files (frontend)
app.mount("/static", StaticFiles(directory="static"), name="static")
# Expose data directory so saved face crops can be viewed by the client
app.mount("/data", StaticFiles(directory="data"), name="data")

face_analyzer: Optional[FaceAnalysis] = None
storage = FaceStorage()


@app.on_event("startup")
def on_startup() -> None:
    global face_analyzer
    face_analyzer = FaceAnalysis(name="buffalo_l", providers=["CPUExecutionProvider"])  # CPU by default
    # Larger det_size increases detection accuracy at the cost of speed
    face_analyzer.prepare(ctx_id=0, det_size=(640, 640))


@app.get("/")
def root() -> FileResponse:
    return FileResponse("static/index.html")


def load_image_as_bgr(image_bytes: bytes) -> np.ndarray:
    image = Image.open(BytesIO(image_bytes)).convert("RGB")
    rgb = np.array(image)
    bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    return bgr


def extract_primary_embedding(bgr_image: np.ndarray) -> Tuple[np.ndarray, List[int]]:
    if face_analyzer is None:
        raise RuntimeError("Face analyzer not initialized")
    faces = face_analyzer.get(bgr_image)
    if not faces:
        raise ValueError("No face detected")
    # Choose the largest face by bbox area
    largest = max(faces, key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]))
    emb = largest.normed_embedding
    if emb is None or emb.size == 0:
        raise ValueError("Failed to compute embedding")
    h, w = bgr_image.shape[:2]
    x1, y1, x2, y2 = largest.bbox
    # Convert to integer pixel coords and clamp to image bounds
    xi1 = int(max(0, min(w - 1, round(float(x1)))))
    yi1 = int(max(0, min(h - 1, round(float(y1)))))
    xi2 = int(max(0, min(w - 1, round(float(x2)))))
    yi2 = int(max(0, min(h - 1, round(float(y2)))))
    bbox: List[int] = [xi1, yi1, xi2, yi2]
    return emb.astype(np.float32), bbox


def _sanitize_identity(name: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_\-]", "_", name).strip("_-")
    return safe or "unknown"


def save_face_crop(
    bgr_image: np.ndarray, bbox: List[int], identity_name: str, ts: Optional[str] = None
) -> Optional[str]:
    try:
        x1, y1, x2, y2 = bbox
        # Add a small margin around the bbox
        h, w = bgr_image.shape[:2]
        margin_x = max(2, int(0.03 * (x2 - x1)))
        margin_y = max(2, int(0.05 * (y2 - y1)))
        x1 = max(0, x1 - margin_x)
        y1 = max(0, y1 - margin_y)
        x2 = min(w - 1, x2 + margin_x)
        y2 = min(h - 1, y2 + margin_y)
        if x2 <= x1 or y2 <= y1:
            return None
        crop = bgr_image[y1:y2, x1:x2]
        safe_name = _sanitize_identity(identity_name)
        folder = Path("data") / "recognized" / safe_name
        folder.mkdir(parents=True, exist_ok=True)
        if ts is None:
            ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
        file_path = folder / f"{ts}.jpg"
        # Save using OpenCV (expects BGR)
        cv2.imwrite(str(file_path), crop)
        # Return URL path that maps via /data mount
        url = f"/data/recognized/{safe_name}/{file_path.name}"
        return url
    except Exception:
        return None


def save_annotated_full_image(
    bgr_image: np.ndarray, bbox: List[int], identity_name: str, category: str = "registered"
) -> Optional[str]:
    try:
        x1, y1, x2, y2 = bbox
        # Draw rectangle
        annotated = bgr_image.copy()
        color = (34, 197, 94)  # green
        thickness = 2
        cv2.rectangle(annotated, (x1, y1), (x2, y2), color, thickness)
        # Label background
        label = identity_name
        font = cv2.FONT_HERSHEY_SIMPLEX
        scale = 0.6
        text_thickness = 2
        (text_w, text_h), baseline = cv2.getTextSize(label, font, scale, text_thickness)
        tx, ty = x1, min(annotated.shape[0] - text_h - 2, y2 + 8)
        cv2.rectangle(
            annotated,
            (tx, ty),
            (tx + text_w + 10, ty + text_h + 8),
            (0, 0, 0),
            thickness=-1,
        )
        cv2.putText(annotated, label, (tx + 5, ty + text_h + 2), font, scale, (226, 232, 240), text_thickness)

        safe_name = _sanitize_identity(identity_name)
        folder = Path("data") / category / safe_name
        folder.mkdir(parents=True, exist_ok=True)
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
        file_path = folder / f"{ts}.jpg"
        cv2.imwrite(str(file_path), annotated)
        return f"/data/{category}/{safe_name}/{file_path.name}"
    except Exception:
        return None


@app.post("/api/register")
async def register_face(name: str = Form(...), image: UploadFile = File(...)) -> JSONResponse:
    if not name or not name.strip():
        raise HTTPException(status_code=400, detail="Name is required")
    content = await image.read()
    try:
        bgr = load_image_as_bgr(content)
        emb, bbox = extract_primary_embedding(bgr)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    storage.add_face(name.strip(), emb)
    annotated_url = save_annotated_full_image(bgr, bbox, name.strip(), category="registered")
    return JSONResponse({"ok": True, "name": name.strip(), "bbox": bbox, "registered_image_url": annotated_url})


@app.post("/api/recognize")
async def recognize_face(image: UploadFile = File(...), threshold: float = Form(0.35)) -> JSONResponse:
    content = await image.read()
    try:
        bgr = load_image_as_bgr(content)
        emb, bbox = extract_primary_embedding(bgr)
    except ValueError:
        return JSONResponse({"ok": True, "recognized": False, "name": None, "score": None})
    match = storage.best_match(emb, threshold=threshold)
    if match is None:
        return JSONResponse({"ok": True, "recognized": False, "name": None, "score": None})
    name, score = match
    h, w = bgr.shape[:2]
    ts_dt = datetime.utcnow()
    ts_str = ts_dt.strftime("%Y%m%d_%H%M%S_%f")
    face_url = save_face_crop(bgr, bbox, name, ts=ts_str)
    return JSONResponse({
        "ok": True,
        "recognized": True,
        "name": name,
        "score": score,
        "bbox": bbox,
        "image_size": [w, h],
        "face_image_url": face_url,
        "recognized_at": ts_dt.isoformat() + "Z",
    })


@app.get("/api/faces")
async def list_faces() -> JSONResponse:
    return JSONResponse({"ok": True, "faces": storage.list_identities_summary()})


@app.post("/api/clear")
async def clear_faces() -> JSONResponse:
    storage.clear()
    return JSONResponse({"ok": True})
