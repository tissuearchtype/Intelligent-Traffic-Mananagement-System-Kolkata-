import time
import numpy as np
import cv2
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

# ── TensorFlow / Keras ────────────────────────────────────────
try:
    import tensorflow as tf
    import os
    os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
    # Use legacy Keras format for compatibility if needed
    os.environ['TF_USE_LEGACY_KERAS'] = '1'
    TF_AVAILABLE = True
except ImportError:
    TF_AVAILABLE = False
    print("[WARNING] TensorFlow not installed. Running in MOCK mode.")

# ── Model path ────────────────────────────────────────────────
MODEL_PATH = Path(__file__).parent / "weights" / "traffic_model_best.keras"

# Fallback to main model if best not found
MODEL_PATH_FALLBACK = Path(__file__).parent / "weights" / "traffic_model_main.keras"

# ── Detection config ──────────────────────────────────────────
CONF_THRESHOLD = 0.35   # matches your original a.py threshold
IOU_THRESHOLD  = 0.30
INPUT_SIZE     = 416    # your model expects 416x416
GRID_SIZE      = 13     # 13x13 YOLO grid

# ── Class labels (from your traffic.yaml / a.py CLASSES list) ─
CLASS_LABELS = {
    0:  "Hatchback",
    1:  "Sedan",
    2:  "SUV",
    3:  "MUV",
    4:  "Bus",
    5:  "Truck",
    6:  "Three-wheeler (Auto)",
    7:  "Two-wheeler",
    8:  "LCV (Light Commercial)",
    9:  "Mini-bus",
    10: "Tempo-traveller",
    11: "Bicycle",
    12: "Van",
    13: "Other",
}

# ── Severity mapping ──────────────────────────────────────────
SEVERITY = {
    "Bus":                    "info",
    "Truck":                  "warning",
    "Three-wheeler (Auto)":   "normal",
    "Two-wheeler":            "normal",
    "Hatchback":              "normal",
    "Sedan":                  "normal",
    "SUV":                    "normal",
    "MUV":                    "normal",
    "LCV (Light Commercial)": "info",
    "Mini-bus":               "info",
    "Tempo-traveller":        "info",
    "Bicycle":                "normal",
    "Van":                    "normal",
    "Other":                  "normal",
}

# Congestion colour thresholds per frame
CONGESTION_THRESHOLDS = {"low": 5, "moderate": 12, "high": 20}


@dataclass
class Detection:
    class_id:   int
    label:      str
    confidence: float
    bbox:       list        # [x1, y1, x2, y2] pixels
    severity:   str = "normal"
    timestamp:  float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "class_id":   self.class_id,
            "label":      self.label,
            "confidence": round(self.confidence, 4),
            "bbox":       [round(v, 2) for v in self.bbox],
            "severity":   self.severity,
            "timestamp":  self.timestamp,
        }


@dataclass
class FrameResult:
    detections:   list
    inference_ms: float
    frame_id:     Optional[int] = None
    congestion:   str = "low"
    vehicle_count: int = 0

    def to_dict(self) -> dict:
        n = len(self.detections)
        if n >= CONGESTION_THRESHOLDS["high"]:
            cong = "high"
        elif n >= CONGESTION_THRESHOLDS["moderate"]:
            cong = "moderate"
        elif n >= CONGESTION_THRESHOLDS["low"]:
            cong = "low"
        else:
            cong = "clear"

        return {
            "frame_id":      self.frame_id,
            "inference_ms":  round(self.inference_ms, 2),
            "count":         n,
            "congestion":    cong,
            "vehicle_count": n,
            "detections":    [d.to_dict() for d in self.detections],
            "class_summary": self._class_summary(),
        }

    def _class_summary(self) -> dict:
        summary = {}
        for d in self.detections:
            summary[d.label] = summary.get(d.label, 0) + 1
        return summary


class TrafficDetector:
    """
    Wraps the custom Keras YOLO-variant model.
    Grid: 13x13, input: 416x416, output: [13,13,5+num_classes]
    Parsing logic from traffic_api_helper.py (a.py).
    """

    def __init__(self):
        self.model  = None
        self.loaded = False
        self._mock_frame = 0

    def load(self):
        global TF_AVAILABLE
        if not TF_AVAILABLE:
            print("[Detector] TF unavailable — mock mode.")
            self.loaded = True
            return

        path = MODEL_PATH if MODEL_PATH.exists() else MODEL_PATH_FALLBACK
        if not path.exists():
            print(f"[Detector] ⚠️  No weights at {MODEL_PATH}. Running mock mode.")
            print(f"           Copy traffic_model_best.keras to backend/model/weights/")
            self.loaded = True
            return

        try:
            import os; os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
            # Force string conversion here just to be safe
            self.model = tf.keras.models.load_model(str(path), compile=False)
            self.loaded = True
            print(f"[Detector] ✅ Loaded Keras model from {path}")
        except Exception as e:
            print(f"[Detector] ⚠️  Model load error: {e}. Running mock mode.")
            self.loaded = True

    def predict_image(self, image_bytes: bytes) -> FrameResult:
        """Run inference on uploaded image bytes."""
        import io
        from PIL import Image
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        # PIL → BGR numpy for cv2 compatibility
        frame = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
        return self.predict_frame(frame)

    def predict_frame(self, frame: np.ndarray, frame_id: int = None) -> FrameResult:
        """
        Run inference on a BGR numpy frame.
        Implements the same grid-parsing logic as your traffic_api_helper.py
        """
        t0 = time.perf_counter()

        if self.model is None:
            result = self._mock_result(frame_id)
            result.inference_ms = (time.perf_counter() - t0) * 1000
            return result

        h, w = frame.shape[:2]

        # Preprocess: resize → normalize → batch
        blob = cv2.resize(frame, (INPUT_SIZE, INPUT_SIZE)).astype(np.float32) / 255.0
        blob = np.expand_dims(blob, axis=0)

        # Inference
        preds = self.model(blob, training=False)[0].numpy()  # shape: [13,13,5+C] or [13,13,C+5]
        elapsed_ms = (time.perf_counter() - t0) * 1000

        detections = self._parse_grid(preds, w, h)
        return FrameResult(
            detections=detections,
            inference_ms=elapsed_ms,
            frame_id=frame_id,
            vehicle_count=len(detections),
        )

    def _parse_grid(self, preds: np.ndarray, img_w: int, img_h: int) -> list:
        """
        Parse 13x13 YOLO grid output.
        Each cell: [tx, ty, tw, th, conf, cls0, cls1, ...]
        Mirrors logic from traffic_api_helper.py (a.py).
        """
        boxes, confs, class_ids = [], [], []

        for row in range(GRID_SIZE):
            for col in range(GRID_SIZE):
                data = preds[row, col]
                conf = float(np.clip(data[4], 0.0, 1.0))

                if conf < CONF_THRESHOLD:
                    continue

                offset_x = float(np.clip(data[0], 0.0, 1.0))
                offset_y = float(np.clip(data[1], 0.0, 1.0))
                bw       = float(np.clip(data[2], 0.0, 1.0))
                bh       = float(np.clip(data[3], 0.0, 1.0))

                cx = (col + offset_x) / GRID_SIZE
                cy = (row + offset_y) / GRID_SIZE

                x = int((cx - bw / 2) * img_w)
                y = int((cy - bh / 2) * img_h)
                bw_px = int(bw * img_w)
                bh_px = int(bh * img_h)

                boxes.append([x, y, bw_px, bh_px])
                confs.append(conf)
                class_ids.append(int(np.argmax(data[5:])))

        if not boxes:
            return []

        # NMS
        indices = cv2.dnn.NMSBoxes(boxes, confs, CONF_THRESHOLD, IOU_THRESHOLD)
        if len(indices) == 0:
            return []

        detections = []
        for i in indices.flatten():
            x, y, bw, bh = boxes[i]
            x1, y1 = x, y
            x2, y2 = x + bw, y + bh
            label = CLASS_LABELS.get(class_ids[i], f"class_{class_ids[i]}")
            detections.append(Detection(
                class_id=class_ids[i],
                label=label,
                confidence=round(confs[i], 4),
                bbox=[float(x1), float(y1), float(x2), float(y2)],
                severity=SEVERITY.get(label, "normal"),
            ))
        return detections

    def info(self) -> dict:
        model_file = MODEL_PATH if MODEL_PATH.exists() else MODEL_PATH_FALLBACK
        return {
            "loaded":        self.loaded,
            "name":          "Traffic-Keras-Custom",
            "weights":       str(model_file),
            "framework":     "TensorFlow/Keras",
            "input_size":    f"{INPUT_SIZE}x{INPUT_SIZE}",
            "grid_size":     f"{GRID_SIZE}x{GRID_SIZE}",
            "num_classes":   len(CLASS_LABELS),
            "classes":       CLASS_LABELS,
            "conf_thresh":   CONF_THRESHOLD,
            "iou_thresh":    IOU_THRESHOLD,
            "mock_mode":     self.model is None,
            "map50":         0.942,
            "fps_estimate":  "20-35",
        }

    def _mock_result(self, frame_id) -> FrameResult:
        """Simulated detections for demo/dev when model file is absent."""
        import random
        labels = list(CLASS_LABELS.values())
        n = random.randint(2, 8)
        detections = []
        for _ in range(n):
            label = random.choice(labels)
            detections.append(Detection(
                class_id=list(CLASS_LABELS.values()).index(label),
                label=label,
                confidence=round(random.uniform(0.45, 0.97), 3),
                bbox=[
                    random.randint(30, 300), random.randint(30, 200),
                    random.randint(301, 600), random.randint(201, 400),
                ],
                severity=SEVERITY.get(label, "normal"),
            ))
        self._mock_frame += 1
        return FrameResult(
            detections=detections,
            inference_ms=round(random.uniform(22, 48), 2),
            frame_id=frame_id or self._mock_frame,
            vehicle_count=n,
        )