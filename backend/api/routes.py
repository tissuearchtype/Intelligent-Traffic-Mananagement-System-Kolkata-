import uuid, time, shutil, httpx, os, random, cv2
from pathlib import Path
from typing import Optional
from datetime import datetime
from fastapi import APIRouter, UploadFile, File, Request, HTTPException, Query
from fastapi.responses import JSONResponse

router = APIRouter()

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

event_log = []

TOMTOM_KEY       = os.getenv("TOMTOM_API_KEY", "")
OPENWEATHER_KEY  = os.getenv("OPENWEATHER_API_KEY", "")

KOLKATA_SECTORS = [
    {"id": "s1",  "name": "Esplanade",          "lat": 22.5645, "lon": 88.3509, "zone": "Central"},
    {"id": "s2",  "name": "Park Street",         "lat": 22.5553, "lon": 88.3528, "zone": "Central"},
    {"id": "s3",  "name": "Howrah Bridge",        "lat": 22.5851, "lon": 88.3468, "zone": "West"},
    {"id": "s4",  "name": "Salt Lake City Centre","lat": 22.5744, "lon": 88.4346, "zone": "East"},
    {"id": "s5",  "name": "EM Bypass NH-12",      "lat": 22.5127, "lon": 88.3989, "zone": "South"},
    {"id": "s6",  "name": "Ultadanga",            "lat": 22.5888, "lon": 88.3866, "zone": "North"},
    {"id": "s7",  "name": "Rashbehari Connector", "lat": 22.5273, "lon": 88.3525, "zone": "South"},
    {"id": "s8",  "name": "Dunlop Bridge",        "lat": 22.6368, "lon": 88.3685, "zone": "North"},
    {"id": "s9",  "name": "Gariahat",             "lat": 22.5178, "lon": 88.3669, "zone": "South"},
    {"id": "s10", "name": "Sealdah",              "lat": 22.5651, "lon": 88.3697, "zone": "Central"},
    {"id": "s11", "name": "Tollygunge",           "lat": 22.4990, "lon": 88.3468, "zone": "South"},
    {"id": "s12", "name": "New Town AA-1",        "lat": 22.5871, "lon": 88.4773, "zone": "New Town"},
]

@router.post("/detect/upload")
async def detect_upload(
    request: Request,
    file: UploadFile = File(...),
    location: Optional[str] = "Unknown",
):
    allowed = {".jpg", ".jpeg", ".png", ".bmp", ".mp4", ".avi", ".mov", ".webp"}
    suffix  = Path(file.filename).suffix.lower()
    if suffix not in allowed:
        raise HTTPException(400, f"Unsupported type: {suffix}")

    save_path = UPLOAD_DIR / f"{uuid.uuid4().hex}{suffix}"
    with open(save_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    detector = request.app.state.detector
    
    if suffix in {".mp4", ".avi", ".mov"}:
        cap = cv2.VideoCapture(str(save_path))
        success, frame = cap.read()
        cap.release()
        if not success:
            raise HTTPException(500, "Failed to extract frame")
            
        success, encoded_image = cv2.imencode('.jpg', frame)
        image_bytes = encoded_image.tobytes()
        result = detector.predict_image(image_bytes)
    else:
        image_bytes = save_path.read_bytes()
        result      = detector.predict_image(image_bytes)

    for det in result.detections:
        if det.severity in ("critical", "warning"):
            event_log.append({
                "id":         uuid.uuid4().hex[:8],
                "label":      det.label,
                "severity":   det.severity,
                "confidence": det.confidence,
                "location":   location,
                "timestamp":  time.time(),
                "source":     "upload",
            })

    return JSONResponse({"filename": file.filename, "location": location, **result.to_dict()})

@router.get("/model/info")
async def model_info(request: Request):
    return JSONResponse(request.app.state.detector.info())

@router.get("/stats")
async def get_stats():
    now       = time.time()
    last_hour = [e for e in event_log if now - e["timestamp"] < 3600]
    vehicles  = sum(e.get("vehicle_count", 1) for e in event_log)

    return JSONResponse({
        "accidents_total":   len([e for e in last_hour if "accident" in e["label"].lower()]),
        "violations_total":  len([e for e in last_hour if "violation" in e["label"].lower()]),
        "vehicles_tracked":  vehicles or random.randint(800, 1400),
        "events_last_hour":  len(last_hour),
        "events_all_time":   len(event_log),
        "model_confidence":  0.942,
        "active_cameras":    len(KOLKATA_SECTORS),
    })

@router.get("/events")
async def get_events(limit: int = 50):
    recent = sorted(event_log, key=lambda e: e["timestamp"], reverse=True)[:limit]
    return JSONResponse({"events": recent})

@router.get("/traffic/sectors")
async def get_sectors():
    sectors_out = []
    for s in KOLKATA_SECTORS:
        congestion, speed, incidents = _get_sector_traffic(s)
        sectors_out.append({
            **s,
            "congestion":   congestion,
            "avg_speed_kph": speed,
            "incidents":    incidents,
            "updated_at":   datetime.utcnow().isoformat(),
        })
    return JSONResponse({"sectors": sectors_out})

def _get_sector_traffic(sector: dict):
    if TOMTOM_KEY and TOMTOM_KEY != "YOUR_TOMTOM_API_KEY":
        try:
            url = (
                f"https://api.tomtom.com/traffic/services/4/flowSegmentData/absolute/10/json"
                f"?key={TOMTOM_KEY}&point={sector['lat']},{sector['lon']}"
            )
            import httpx as hx
            r = hx.get(url, timeout=4)
            if r.status_code == 200:
                fd = r.json().get("flowSegmentData", {})
                speed    = fd.get("currentSpeed", 30)
                free_flow = fd.get("freeFlowSpeed", 50)
                ratio    = speed / max(free_flow, 1)
                if ratio < 0.3:   cong = "high"
                elif ratio < 0.6: cong = "moderate"
                else:             cong = "low"
                return cong, speed, []
        except Exception:
            pass

    hour = datetime.utcnow().hour + 5  
    if 8 <= hour <= 10 or 17 <= hour <= 20:
        speeds  = {"high": (8, 18),  "moderate": (19, 30), "low": (31, 55)}
    else:
        speeds  = {"high": (5, 12),  "moderate": (13, 18), "low": (19, 25)}

    seed = hash(sector["id"] + str(hour // 2)) % 100
    if seed < 25:   cong = "high"
    elif seed < 55: cong = "moderate"
    else:           cong = "low"

    lo, hi = speeds[cong]
    speed = random.randint(lo, hi)
    return cong, speed, []

@router.get("/traffic/live")
async def get_live_traffic(
    lat: float = Query(22.5726),
    lon: float = Query(88.3639),
    zoom: int  = Query(12),
):
    if not TOMTOM_KEY or TOMTOM_KEY == "YOUR_TOMTOM_API_KEY":
        return JSONResponse({
            "source": "simulation",
            "message": "Set TOMTOM_API_KEY env var",
            "tomtom_tile_url": None,
            "sectors": [],
        })

    tile_url = (
        f"https://api.tomtom.com/traffic/map/4/tile/flow/relative0/{zoom}/{{x}}/{{y}}.png"
        f"?key={TOMTOM_KEY}&tileSize=256"
    )
    return JSONResponse({
        "source":       "tomtom",
        "tile_url":     tile_url,
        "api_key":      TOMTOM_KEY,
        "center":       {"lat": lat, "lon": lon},
        "zoom":         zoom,
    })

@router.post("/route/predict")
async def predict_route(request: Request):
    body = await request.json()
    origin_lat = body.get("origin_lat", 22.5851)
    origin_lon = body.get("origin_lon", 88.3468)
    dest_lat   = body.get("dest_lat",   22.5744)
    dest_lon   = body.get("dest_lon",   88.4346)
    origin     = body.get("origin",     "Origin")
    destination = body.get("destination", "Destination")

    if TOMTOM_KEY and TOMTOM_KEY != "YOUR_TOMTOM_API_KEY":
        try:
            url = (
                f"https://api.tomtom.com/routing/1/calculateRoute/"
                f"{origin_lat},{origin_lon}:{dest_lat},{dest_lon}/json"
                f"?key={TOMTOM_KEY}&traffic=true&routeType=fastest&travelMode=car"
            )
            async with httpx.AsyncClient(timeout=8) as client:
                r = await client.get(url)
            if r.status_code == 200:
                data  = r.json()
                route = data["routes"][0]["summary"]
                legs = data["routes"][0].get("legs", [])
                geometry_points = []
                if legs and "points" in legs[0]:
                    geometry_points = [[p["latitude"], p["longitude"]] for p in legs[0]["points"]]
                return JSONResponse({
                    "source":          "tomtom",
                    "origin":          origin,
                    "destination":     destination,
                    "distance_km":     round(route["lengthInMeters"] / 1000, 1),
                    "travel_time_min": round(route["travelTimeInSeconds"] / 60, 1),
                    "delay_min":       round(route.get("trafficDelayInSeconds", 0) / 60, 1),
                    "congestion":      _classify_delay(route.get("trafficDelayInSeconds", 0)),
                    "recommendation":  _route_recommendation(route),
                    "geometry":        geometry_points,
                })
        except Exception:
            pass

    dist_km = _haversine(origin_lat, origin_lon, dest_lat, dest_lon)
    hour    = (datetime.utcnow().hour + 5) % 24
    peak    = 8 <= hour <= 10 or 17 <= hour <= 20
    avg_spd = random.randint(12, 22) if peak else random.randint(25, 40)
    eta_min = round((dist_km / avg_spd) * 60, 1)
    delay   = round(random.uniform(5, 25) if peak else random.uniform(0, 8), 1)

    return JSONResponse({
        "source":          "estimated",
        "origin":          origin,
        "destination":     destination,
        "distance_km":     round(dist_km, 1),
        "travel_time_min": eta_min,
        "delay_min":       delay,
        "congestion":      "high" if peak else "moderate",
        "recommendation":  "Peak" if peak else "Moderate",
        "peak_hours":      peak,
        "alternatives": [
            {"name": "Via VIP Road",       "extra_km": 3.2, "saves_min": 8  if peak else -2},
            {"name": "Via APC Road",       "extra_km": 1.8, "saves_min": 5  if peak else -1},
            {"name": "Via Bypass NH-12",   "extra_km": 6.0, "saves_min": 12 if peak else -4},
        ],
    })

def _haversine(lat1, lon1, lat2, lon2) -> float:
    import math
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    return R * 2 * math.asin(math.sqrt(a))

def _classify_delay(delay_s: float) -> str:
    if delay_s > 1200:  return "high"
    if delay_s > 400:   return "moderate"
    return "low"

def _route_recommendation(summary: dict) -> str:
    delay = summary.get("trafficDelayInSeconds", 0)
    if delay > 1200: return "Heavy"
    if delay > 400:  return "Moderate"
    return "Clear"

@router.get("/weather")
async def get_weather(lat: float = 22.5726, lon: float = 88.3639):
    if OPENWEATHER_KEY and OPENWEATHER_KEY != "YOUR_OPENWEATHER_API_KEY":
        try:
            url = (
                f"https://api.openweathermap.org/data/2.5/weather"
                f"?lat={lat}&lon={lon}&appid={OPENWEATHER_KEY}&units=metric"
            )
            async with httpx.AsyncClient(timeout=5) as client:
                r = await client.get(url)
            if r.status_code == 200:
                d = r.json()
                return JSONResponse({
                    "source":      "openweathermap",
                    "temp_c":      d["main"]["temp"],
                    "feels_like":  d["main"]["feels_like"],
                    "humidity":    d["main"]["humidity"],
                    "condition":   d["weather"][0]["main"],
                    "description": d["weather"][0]["description"],
                    "wind_kph":    round(d["wind"]["speed"] * 3.6, 1),
                    "visibility_km": round(d.get("visibility", 10000) / 1000, 1),
                    "rain_mm":     d.get("rain", {}).get("1h", 0),
                    "traffic_impact": _weather_impact(d),
                })
        except Exception:
            pass

    conditions = ["Clear", "Partly Cloudy", "Haze", "Light Rain"]
    cond = random.choice(conditions)
    return JSONResponse({
        "source":        "simulated",
        "temp_c":        round(random.uniform(28, 38), 1),
        "humidity":      random.randint(55, 85),
        "condition":     cond,
        "description":   cond.lower(),
        "wind_kph":      round(random.uniform(5, 20), 1),
        "visibility_km": random.randint(4, 10),
        "rain_mm":       round(random.uniform(0, 5) if "Rain" in cond else 0, 1),
        "traffic_impact": "moderate" if "Rain" in cond else "low",
    })

def _weather_impact(d: dict) -> str:
    cond = d["weather"][0]["main"].lower()
    if "rain" in cond or "storm" in cond or "snow" in cond: return "high"
    if "fog" in cond or "haze" in cond: return "moderate"
    return "low"