# Intelligent Traffic Management System — Kolkata
### Full-stack: FastAPI Backend + Leaflet Map + Keras Model Integration

---

## Project Structure

```
traffic_system/
│
├── backend/
│   ├── main.py                     ← FastAPI entry point
│   ├── api/
│   │   ├── routes.py               ← REST endpoints
│   │   └── websocket.py            ← Live camera WebSocket
│   └── model/
│       ├── detector.py             ← ★ YOUR KERAS MODEL IS WIRED HERE ★
│       └── weights/
│           ├── traffic_model_best.keras   ← ★ PUT YOUR MODEL HERE ★
│           └── traffic_model_main.keras   ← (fallback)
│
├── frontend/
│   ├── templates/dashboard.html    ← Main dashboard
│   └── static/
│       ├── css/dashboard.css
│       └── js/dashboard.js
│
├── uploads/                        ← Auto-created
├── requirements.txt
└── README.md
```

---

## Quick Start (5 steps)

### 1. Copy your model weights
```bash
# From the uploaded zip:
cp traffic_model_best.keras  backend/model/weights/
cp traffic_model_main.keras  backend/model/weights/
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```
> For GPU: `pip install tensorflow[and-cuda]` instead of `tensorflow-cpu`

### 3. (Optional) Set API keys for live data
```bash
# Windows:
set TOMTOM_API_KEY=your_key_here
set OPENWEATHER_API_KEY=your_key_here

# Linux/Mac:
export TOMTOM_API_KEY=your_key_here
export OPENWEATHER_API_KEY=your_key_here
```
**Without keys**, the system runs in simulation mode (realistic fake data).
Get free keys at: https://developer.tomtom.com  and  https://openweathermap.org/api

### 4. Run the server
```bash
# From the traffic_system/ folder:
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

### 5. Open the dashboard
```
http://localhost:8000
```

---

## Model Details

| Property | Value |
|----------|-------|
| File | `traffic_model_best.keras` |
| Framework | TensorFlow / Keras |
| Input size | 416 × 416 |
| Grid | 13 × 13 YOLO-style |
| Output format | `[13, 13, 5 + num_classes]` |
| Confidence threshold | 0.35 |
| IOU threshold (NMS) | 0.30 |
| Classes | 14 (Hatchback, Sedan, SUV, MUV, Bus, Truck, Auto, Two-wheeler, LCV, Mini-bus, Tempo, Bicycle, Van, Other) |

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Dashboard UI |
| POST | `/api/detect/upload` | Upload image/video → model inference |
| GET | `/api/model/info` | Model metadata + class list |
| GET | `/api/stats` | KPI stats (accidents, violations, vehicles) |
| GET | `/api/events` | Recent detection log |
| GET | `/api/traffic/sectors` | Kolkata 12-sector congestion status |
| GET | `/api/traffic/live` | TomTom live flow tile config |
| POST | `/api/route/predict` | Route + ETA prediction |
| GET | `/api/weather` | Weather + traffic impact |
| WS | `/ws/stream` | Live camera frame stream → detections |
| WS | `/ws/alerts` | Push alert feed |

---

## Features

- **Upload analysis** — drag and drop any traffic image/video, run your Keras model, see bboxes + vehicle types
- **Live camera** — WebSocket stream from browser camera, real-time bbox overlay on video
- **Kolkata sector map** — 12 key junctions with colour-coded congestion markers (Leaflet + CartoDB dark tiles)
- **Route prediction** — origin → destination with ETA, delay, congestion, and 3 alternatives
- **Weather impact** — real weather data affects traffic prediction context
- **Model status card** — shows your model name, MAP@0.5, classes, conf threshold, framework
- **Live event feed** — scrolling log of all detections with severity colour coding
- **Vehicle breakdown chart** — Chart.js bar chart of detected vehicle types

---

## Expanding to All India

The system is designed to scale. To add cities:
1. Add sector coordinates to `KOLKATA_SECTORS` in `routes.py`
2. Change map center in `dashboard.js` `KOLKATA` const
3. Add city selector to the frontend

---

## Troubleshooting

**"Model weights not found"** → Copy `.keras` files to `backend/model/weights/`

**TF import error** → `pip install tensorflow-cpu==2.15.0`

**CORS error in browser** → Make sure you're accessing via `http://localhost:8000`, not opening the HTML file directly

**Camera not working** → Browser requires HTTPS for camera access on non-localhost. For local dev, `localhost` is fine.

**TomTom 403** → API key is wrong or not activated. The system falls back to simulation automatically.
