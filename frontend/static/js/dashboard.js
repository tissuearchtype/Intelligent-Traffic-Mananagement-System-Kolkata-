/**
 * ITMS Dashboard — Kolkata Traffic Intelligence
 * dashboard.js
 */

const API = '';   // same origin; change to 'http://localhost:8000' if served separately

// ── Clock ──────────────────────────────────────────────────────
function updateClock() {
  const now = new Date();
  document.getElementById('clock').textContent =
    now.toLocaleTimeString('en-IN', { timeZone: 'Asia/Kolkata', hour12: false });
}
setInterval(updateClock, 1000);
updateClock();

// ── Tab switching ──────────────────────────────────────────────
function switchTab(name, btn) {
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  btn.classList.add('active');
  document.getElementById('tab-upload').classList.toggle('hidden', name !== 'upload');
  document.getElementById('tab-camera').classList.toggle('hidden', name !== 'camera');
}

// ── Drag-and-drop ─────────────────────────────────────────────
const dropZone = document.getElementById('dropZone');
['dragenter','dragover'].forEach(e => dropZone.addEventListener(e, ev => { ev.preventDefault(); dropZone.classList.add('dragging'); }));
['dragleave','drop'].forEach(e => dropZone.addEventListener(e, ev => { ev.preventDefault(); dropZone.classList.remove('dragging'); }));
dropZone.addEventListener('drop', ev => {
  const file = ev.dataTransfer.files[0];
  if (file) { document.getElementById('fileInput').files = ev.dataTransfer.files; dropZone.querySelector('.drop-text').textContent = file.name; }
});
document.getElementById('fileInput').addEventListener('change', ev => {
  const f = ev.target.files[0];
  if (f) dropZone.querySelector('.drop-text').textContent = f.name;
});

// ── Run Analysis ──────────────────────────────────────────────
async function runAnalysis() {
  const file     = document.getElementById('fileInput').files[0];
  const location = document.getElementById('locationSelect').value || 'Unknown';
  const btn      = document.getElementById('runBtn');
  const panel    = document.getElementById('uploadResult');

  if (!file) { alert('Please select a file first.'); return; }

  btn.disabled = true;
  btn.textContent = '⌛ ANALYSING…';
  panel.classList.add('hidden');

  const form = new FormData();
  form.append('file', file);
  form.append('location', location);

  try {
    const res  = await fetch(`${API}/api/detect/upload`, { method: 'POST', body: form });
    const data = await res.json();
    renderUploadResult(data, panel);
    addToEventFeed(data);
  } catch (err) {
    panel.innerHTML = `<div style="color:var(--critical)">Error: ${err.message}</div>`;
    panel.classList.remove('hidden');
  } finally {
    btn.disabled = false;
    btn.textContent = '▶ RUN ANALYSIS';
  }
}

function renderUploadResult(data, panel) {
  const dets = data.detections || [];
  let html = `
    <div style="margin-bottom:8px;color:var(--text-bright);font-weight:600;">
      ✓ ${data.filename} · ${data.count} detections
    </div>
    <div style="margin-bottom:6px;color:var(--text-dim);font-size:11px;">
      Congestion: <span style="color:${congColor(data.congestion)}">${(data.congestion||'—').toUpperCase()}</span>
    </div>`;

  if (dets.length === 0) {
    html += '<div style="color:var(--text-dim)">No detections above threshold.</div>';
  } else {
    dets.forEach(d => {
      html += `<div class="det-row">
        <span class="det-label">${d.label}</span>
        <span class="det-conf">${(d.confidence*100).toFixed(1)}%</span>
        <span class="det-sev-${d.severity}">${d.severity}</span>
      </div>`;
    });
  }

  if (data.class_summary) {
    html += `<div style="margin-top:8px;font-size:11px;color:var(--text-dim);">`;
    for (const [cls, cnt] of Object.entries(data.class_summary)) {
      html += `<span style="margin-right:10px;">${cls}: <b style="color:var(--text)">${cnt}</b></span>`;
    }
    html += '</div>';
  }

  panel.innerHTML = html;
  panel.classList.remove('hidden');
}

function congColor(c) {
  if (c === 'high')     return 'var(--critical)';
  if (c === 'moderate') return 'var(--warning)';
  if (c === 'clear' || c === 'low') return 'var(--success)';
  return 'var(--info)';
}

// ── Event Feed ────────────────────────────────────────────────
const DEMO_EVENTS = [
  { label: 'Truck', severity: 'warning',  location: 'Howrah Bridge · Cam-03',  ts: Date.now() - 12000 },
  { label: 'Bus',   severity: 'info',     location: 'EM Bypass NH-12 · Cam-05', ts: Date.now() - 45000 },
  { label: 'Auto',  severity: 'normal',   location: 'Park Street · Cam-02',    ts: Date.now() - 90000 },
];

function addToEventFeed(data) {
  const feed = document.getElementById('eventFeed');
  const placeholder = feed.querySelector('.event-placeholder');
  if (placeholder) placeholder.remove();

  (data.detections || []).forEach(d => {
    const ago = 'just now';
    const item = document.createElement('div');
    item.className = `event-item ${d.severity}`;
    item.innerHTML = `
      <div class="event-dot"></div>
      <div class="event-body">
        <div class="event-title">${d.label} detected</div>
        <div class="event-meta">${data.location || 'Unknown'} · ${(d.confidence*100).toFixed(1)}% conf</div>
        <div class="event-bar"></div>
      </div>
      <div class="event-time">${ago}</div>`;
    feed.prepend(item);
  });
}

function populateDemoFeed() {
  const feed = document.getElementById('eventFeed');
  feed.innerHTML = '';
  DEMO_EVENTS.forEach(e => {
    const secAgo = Math.round((Date.now() - e.ts) / 1000);
    const ago    = secAgo < 60 ? `${secAgo}s ago` : `${Math.round(secAgo/60)}m ago`;
    feed.innerHTML += `
      <div class="event-item ${e.severity}">
        <div class="event-dot"></div>
        <div class="event-body">
          <div class="event-title">${e.label} detected</div>
          <div class="event-meta">${e.location}</div>
          <div class="event-bar"></div>
        </div>
        <div class="event-time">${ago}</div>
      </div>`;
  });
}
populateDemoFeed();

// ── Stats polling ─────────────────────────────────────────────
async function pollStats() {
  try {
    const r = await fetch(`${API}/api/stats`);
    const d = await r.json();
    document.getElementById('kpiAccidents').textContent   = d.accidents_total  ?? '0';
    document.getElementById('kpiViolations').textContent  = d.violations_total ?? '0';
    document.getElementById('kpiVehicles').textContent    = (d.vehicles_tracked||0).toLocaleString('en-IN');
    document.getElementById('kpiConfidence').textContent  = ((d.model_confidence||0.942)*100).toFixed(1) + '%';
    document.getElementById('kpiAccidentsSub').textContent  = `↑ ${d.accidents_total||0} this hour`;
    document.getElementById('kpiViolationsSub').textContent = `${d.violations_total||0} in queue`;
    document.getElementById('kpiVehiclesSub').textContent   = `${d.active_cameras||12} cams active`;
  } catch { /* backend not started yet */ }
}
pollStats();
setInterval(pollStats, 30000);

// ── Model Info ────────────────────────────────────────────────
async function loadModelInfo() {
  try {
    const r = await fetch(`${API}/api/model/info`);
    const d = await r.json();

    document.getElementById('modelBadge').textContent = d.mock_mode ? '⬡ DEMO MODE' : '⬡ MODEL ACTIVE';
    document.getElementById('modelName').textContent  = d.name || 'Traffic-Keras-Custom';
    document.getElementById('modelMeta').textContent  =
      `${d.framework||'TensorFlow/Keras'} · ${d.input_size||'416×416'} · ${d.grid_size||'13×13'} grid`;

    document.getElementById('modelGrid').innerHTML = `
      <div class="model-stat"><div class="model-stat-label">MAP@0.5</div><div class="model-stat-val">${d.map50||0.942}</div></div>
      <div class="model-stat"><div class="model-stat-label">FPS EST.</div><div class="model-stat-val">${d.fps_estimate||'20-35'}</div></div>
      <div class="model-stat"><div class="model-stat-label">CLASSES</div><div class="model-stat-val">${d.num_classes||14}</div></div>
      <div class="model-stat"><div class="model-stat-label">CONF THRESH</div><div class="model-stat-val">${d.conf_thresh||0.35}</div></div>`;

    const classes = d.classes || {};
    const typeMap  = { 'Bus':'bus','Truck':'truck','Two-wheeler':'auto','Hatchback':'vehicle','Sedan':'vehicle','SUV':'vehicle','MUV':'vehicle' };
    document.getElementById('modelClasses').innerHTML =
      Object.values(classes).map(c => `<span class="cls-chip ${typeMap[c]||''}">${c}</span>`).join('');

  } catch { document.getElementById('modelBadge').textContent = '⬡ BACKEND OFFLINE'; }
}
loadModelInfo();

// ── Map ───────────────────────────────────────────────────────
const KOLKATA = [22.5726, 88.3639];
let map, sectorMarkers = [];
let routeLayer = null, routeMarkers = [];

function initMap() {
  map = L.map('map', { zoomControl: true, attributionControl: false }).setView(KOLKATA, 12);

  L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
    attribution: '© CartoDB',
    subdomains: 'abcd', maxZoom: 19,
  }).addTo(map);

  loadSectors();
}

async function loadSectors() {
  try {
    const r = await fetch(`${API}/api/traffic/sectors`);
    const d = await r.json();
    renderSectors(d.sectors || []);
  } catch {
    renderSectors(DEMO_SECTORS);
  }
}

const DEMO_SECTORS = [
  { id:'s1',  name:'Esplanade',           lat:22.5645, lon:88.3509, congestion:'moderate', avg_speed_kph:22 },
  { id:'s2',  name:'Park Street',          lat:22.5553, lon:88.3528, congestion:'low',      avg_speed_kph:38 },
  { id:'s3',  name:'Howrah Bridge',         lat:22.5851, lon:88.3468, congestion:'high',     avg_speed_kph:12 },
  { id:'s4',  name:'Salt Lake City Centre', lat:22.5744, lon:88.4346, congestion:'low',      avg_speed_kph:42 },
  { id:'s5',  name:'EM Bypass NH-12',       lat:22.5127, lon:88.3989, congestion:'high',     avg_speed_kph:15 },
  { id:'s6',  name:'Ultadanga',             lat:22.5888, lon:88.3866, congestion:'moderate', avg_speed_kph:25 },
  { id:'s7',  name:'Rashbehari Connector',  lat:22.5273, lon:88.3525, congestion:'moderate', avg_speed_kph:20 },
  { id:'s8',  name:'Dunlop Bridge',         lat:22.6368, lon:88.3685, congestion:'low',      avg_speed_kph:35 },
  { id:'s9',  name:'Gariahat',              lat:22.5178, lon:88.3669, congestion:'high',     avg_speed_kph:14 },
  { id:'s10', name:'Sealdah',               lat:22.5651, lon:88.3697, congestion:'moderate', avg_speed_kph:24 },
  { id:'s11', name:'Tollygunge',            lat:22.4990, lon:88.3468, congestion:'low',      avg_speed_kph:36 },
  { id:'s12', name:'New Town AA-1',         lat:22.5871, lon:88.4773, congestion:'low',      avg_speed_kph:48 },
];

function congMarkerColor(c) {
  if (c === 'high')     return '#ff3b5c';
  if (c === 'moderate') return '#ffaa00';
  return '#00e87a';
}

function renderSectors(sectors) {
  sectorMarkers.forEach(m => map.removeLayer(m));
  sectorMarkers = [];

  sectors.forEach(s => {
    const col  = congMarkerColor(s.congestion);
    const icon = L.divIcon({
      className: '',
      html: `<div style="width:14px;height:14px;border-radius:50%;background:${col};border:2px solid rgba(255,255,255,0.3);box-shadow:0 0 8px ${col}88;"></div>`,
      iconSize: [14, 14], iconAnchor: [7, 7],
    });
    const m = L.marker([s.lat, s.lon], { icon })
      .addTo(map)
      .bindPopup(`
        <div style="font-family:JetBrains Mono,monospace;min-width:160px;">
          <div style="font-weight:700;font-size:13px;margin-bottom:4px;">${s.name}</div>
          <div style="font-size:11px;color:#5a7a9a;">Speed: <b style="color:#e8f4ff">${s.avg_speed_kph} km/h</b></div>
          <div style="font-size:11px;color:#5a7a9a;">Status: <b style="color:${col}">${s.congestion.toUpperCase()}</b></div>
        </div>`);
    sectorMarkers.push(m);
  });

  const list = document.getElementById('sectorList');
  list.innerHTML = sectors.map(s => `
    <div class="sector-row">
      <span class="sector-name">${s.name}</span>
      <span class="sector-speed">${s.avg_speed_kph} km/h</span>
      <span class="sector-badge ${s.congestion}">${s.congestion.toUpperCase()}</span>
    </div>`).join('');
}

initMap();
setInterval(loadSectors, 60000);

// ── Helper: Convert Text to Coordinates (Geocoding) ───────────
async function getCoordinates(placeName) {
  try {
    // We add 'viewbox' and 'bounded=1' to force results to stay near Kolkata
    const kolkataBounds = "88.15,22.75,88.55,22.35"; 
    const url = `https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(placeName)}&viewbox=${kolkataBounds}&bounded=1&limit=1`;
    
    const res = await fetch(url);
    const data = await res.json();
    if (data && data.length > 0) {
      return { lat: parseFloat(data[0].lat), lon: parseFloat(data[0].lon) };
    }
  } catch (e) {
    console.warn("Geocoding failed", e);
  }
  return null;
}

// ── Route Prediction ──────────────────────────────────────────
function clearRouteFromMap() {
  if (routeLayer) { map.removeLayer(routeLayer); routeLayer = null; }
  routeMarkers.forEach(m => map.removeLayer(m));
  routeMarkers = [];
}

function makeEndpointMarker(latlng, color, label) {
  const icon = L.divIcon({
    className: '',
    html: `<div style="
      width:18px;height:18px;border-radius:50%;
      background:${color};border:3px solid #fff;
      box-shadow:0 0 12px ${color};
      display:flex;align-items:center;justify-content:center;
      font-size:8px;font-weight:700;color:#000;font-family:JetBrains Mono,monospace;
    ">${label}</div>`,
    iconSize: [18,18], iconAnchor: [9,9],
  });
  return L.marker(latlng, { icon });
}

async function predictRoute() {
  const originName = document.getElementById('routeOrigin').value.trim()    || 'Howrah Bridge';
  const destName   = document.getElementById('routeDest').value.trim()      || 'Salt Lake';
  
  let originLat  = parseFloat(document.getElementById('routeOriginLat').value);
  let originLon  = parseFloat(document.getElementById('routeOriginLon').value);
  let destLat    = parseFloat(document.getElementById('routeDestLat').value);
  let destLon    = parseFloat(document.getElementById('routeDestLon').value);

  const panel = document.getElementById('routeResult');
  panel.innerHTML = '<div style="color:var(--text-dim);padding:8px 0;">⟳ Locating places and calculating route…</div>';
  panel.classList.remove('hidden');

  if (isNaN(originLat) || isNaN(originLon)) {
    const coords = await getCoordinates(originName);
    if (coords) { originLat = coords.lat; originLon = coords.lon; }
    else { originLat = 22.5851; originLon = 88.3468; } 
  }
  if (isNaN(destLat) || isNaN(destLon)) {
    const coords = await getCoordinates(destName);
    if (coords) { destLat = coords.lat; destLon = coords.lon; }
    else { destLat = 22.5744; destLon = 88.4346; } 
  }

  const body = {
    origin:      originName,
    destination: destName,
    origin_lat:  originLat,
    origin_lon:  originLon,
    dest_lat:    destLat,
    dest_lon:    destLon,
  };

  clearRouteFromMap();

  try {
    const r = await fetch(`${API}/api/route/predict`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    const d = await r.json();

    const routeColor = congMarkerColor(d.congestion);

    if (d.geometry && d.geometry.length > 1) {
      routeLayer = L.polyline(d.geometry, {
        color:       routeColor,
        weight:      4,
        opacity:     0.9,
        smoothFactor: 1,
        lineJoin:    'round',
        lineCap:     'round',
      }).addTo(map);
      map.fitBounds(routeLayer.getBounds(), { padding: [50, 50] });
    } else {
      routeLayer = L.polyline(
        [[originLat, originLon], [destLat, destLon]],
        { color: routeColor, weight: 3, opacity: 0.75, dashArray: '10 7' }
      ).addTo(map);
      map.fitBounds([[originLat, originLon], [destLat, destLon]], { padding: [60, 60] });
    }

    const mOrigin = makeEndpointMarker([originLat, originLon], '#00e87a', 'A')
      .bindPopup(`<b>Origin:</b> ${d.origin}`)
      .addTo(map);
    const mDest = makeEndpointMarker([destLat, destLon], '#ff3b5c', 'B')
      .bindPopup(`<b>Destination:</b> ${d.destination}`)
      .addTo(map);
    routeMarkers = [mOrigin, mDest];

    const alts = (d.alternatives || []).map(a =>
      `<div class="route-alt-row">
         <span>${a.name}</span>
         <span style="color:var(--text-dim)">+${a.extra_km}km</span>
         <span class="alt-save ${a.saves_min > 0 ? 'good':'bad'}">${a.saves_min > 0 ? '−'+a.saves_min+'min' : '+'+Math.abs(a.saves_min)+'min'}</span>
       </div>`).join('');

    const sourceTag = d.source === 'tomtom'
      ? `<span style="font-size:10px;color:#00e87a;font-family:var(--font-mono);">● LIVE / TOMTOM</span>`
      : `<span style="font-size:10px;color:#ffaa00;font-family:var(--font-mono);">◎ ESTIMATED</span>`;

    panel.innerHTML = `
      <div class="route-head" style="display:flex;justify-content:space-between;align-items:center;">
        <span>${d.origin} → ${d.destination}</span>
        ${sourceTag}
      </div>
      <div class="route-meta">
        <div class="route-stat">
          <div class="route-stat-label">DISTANCE</div>
          <div class="route-stat-val">${d.distance_km} km</div>
        </div>
        <div class="route-stat">
          <div class="route-stat-label">ETA</div>
          <div class="route-stat-val">${d.travel_time_min} min</div>
        </div>
        <div class="route-stat">
          <div class="route-stat-label">DELAY</div>
          <div class="route-stat-val" style="color:${congColor(d.congestion)}">${d.delay_min} min</div>
        </div>
        <div class="route-stat">
          <div class="route-stat-label">TRAFFIC</div>
          <div class="route-stat-val" style="color:${congColor(d.congestion)}">${(d.congestion||'').toUpperCase()}</div>
        </div>
      </div>
      <div class="route-reco">${d.recommendation}</div>
      ${alts ? `<div class="route-alts"><div style="font-size:10px;color:var(--text-dim);margin-bottom:4px;font-family:var(--font-mono);">ALTERNATIVES</div>${alts}</div>` : ''}
    `;
  } catch (err) {
    panel.innerHTML = `<div style="color:var(--critical)">Error: ${err.message}</div>`;
  }
}

// ── Weather ───────────────────────────────────────────────────
async function loadWeather() {
  try {
    const r = await fetch(`${API}/api/weather`);
    const d = await r.json();
    document.getElementById('weatherTemp').textContent = `${d.temp_c}°C`;
    document.getElementById('weatherCond').textContent = d.description || d.condition;
    document.getElementById('weatherDetails').innerHTML = `
      <div class="wx-stat"><div class="wx-label">HUMIDITY</div><div class="wx-val">${d.humidity}%</div></div>
      <div class="wx-stat"><div class="wx-label">WIND</div><div class="wx-val">${d.wind_kph} km/h</div></div>
      <div class="wx-stat"><div class="wx-label">VISIB.</div><div class="wx-val">${d.visibility_km} km</div></div>
    `;
    const impactColor = d.traffic_impact === 'high' ? 'var(--critical)' : d.traffic_impact === 'moderate' ? 'var(--warning)' : 'var(--success)';
    document.getElementById('weatherImpact').innerHTML =
      `<span style="color:var(--text-dim)">Traffic impact: </span><b style="color:${impactColor}">${(d.traffic_impact||'low').toUpperCase()}</b>` +
      (d.rain_mm > 0 ? ` · Rain ${d.rain_mm}mm/h` : '');
  } catch { document.getElementById('weatherCond').textContent = 'Weather unavailable (set OPENWEATHER_API_KEY)'; }
}
loadWeather();
setInterval(loadWeather, 300000);

// ── Vehicle Chart ─────────────────────────────────────────────
const VEHICLE_CLASSES  = ['Hatchback','Sedan','SUV','MUV','Bus','Truck','Auto','Two-wheeler','LCV','Mini-bus','Bicycle','Van'];
const VEHICLE_COUNTS   = [220, 185, 142, 88, 64, 52, 198, 315, 38, 22, 45, 30];
const CHART_COLORS     = ['#00d4ff','#0088bb','#00e87a','#ffaa00','#ff3b5c','#cc2244','#88bbff','#55ddaa','#ffcc44','#ff7755','#aaffcc','#ccbbff'];

const vehicleCtx = document.getElementById('vehicleChart').getContext('2d');
new Chart(vehicleCtx, {
  type: 'bar',
  data: {
    labels: VEHICLE_CLASSES,
    datasets: [{
      label: 'Vehicles detected',
      data:  VEHICLE_COUNTS,
      backgroundColor: CHART_COLORS.map(c => c + 'aa'),
      borderColor:     CHART_COLORS,
      borderWidth: 1,
      borderRadius: 3,
    }]
  },
  options: {
    responsive: true,
    plugins: { legend: { display: false } },
    scales: {
      x: { ticks: { color: '#5a7a9a', font: { family: 'JetBrains Mono', size: 10 } }, grid: { color: '#1e2d3d' } },
      y: { ticks: { color: '#5a7a9a', font: { family: 'JetBrains Mono', size: 10 } }, grid: { color: '#1e2d3d' } },
    }
  }
});

// ── Live Camera WebSocket ─────────────────────────────────────
let cameraStream = null, wsStream = null, streamInterval = null;
let frameCount = 0, lastFPSTime = Date.now();

async function startCamera() {
  try {
    cameraStream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' }, audio: false });
    const video  = document.getElementById('cameraFeed');
    video.srcObject = cameraStream;

    document.getElementById('camStartBtn').classList.add('hidden');
    document.getElementById('camStopBtn').classList.remove('hidden');
    document.getElementById('streamStats').classList.remove('hidden');

    const wsProto = location.protocol === 'https:' ? 'wss' : 'ws';
    const wsUrl   = `${wsProto}://${location.host}/ws/stream`;
    wsStream = new WebSocket(wsUrl);

    wsStream.onopen    = () => console.log('[WS] Stream connected');
    wsStream.onmessage = (e) => handleStreamResult(JSON.parse(e.data));
    wsStream.onerror   = (e) => console.warn('[WS] Error:', e);
    wsStream.onclose   = ()  => console.log('[WS] Stream closed');

    const canvas = document.createElement('canvas');
    streamInterval = setInterval(() => {
      if (!video.readyState) return;
      canvas.width  = video.videoWidth  || 640;
      canvas.height = video.videoHeight || 480;
      canvas.getContext('2d').drawImage(video, 0, 0);
      canvas.toBlob(blob => {
        if (wsStream?.readyState === WebSocket.OPEN) wsStream.send(blob);
      }, 'image/jpeg', 0.7);
    }, 125);  // 8fps

  } catch (err) {
    alert(`Camera error: ${err.message}`);
  }
}

function handleStreamResult(data) {
  if (data.error) return;

  frameCount++;
  const now = Date.now();
  if (now - lastFPSTime >= 1000) {
    document.getElementById('streamFPS').textContent = `${frameCount} fps`;
    frameCount = 0; lastFPSTime = now;
  }

  document.getElementById('streamVehicles').textContent   = `${data.vehicle_count||0} vehicles`;
  document.getElementById('streamCongestion').textContent = (data.congestion||'clear').toUpperCase();

  const overlay = document.getElementById('overlayCanvas');
  const video   = document.getElementById('cameraFeed');
  overlay.width  = video.offsetWidth;
  overlay.height = video.offsetHeight;
  const ctx = overlay.getContext('2d');
  ctx.clearRect(0, 0, overlay.width, overlay.height);

  (data.detections || []).forEach(d => {
    const scaleX = overlay.width  / (video.videoWidth  || 640);
    const scaleY = overlay.height / (video.videoHeight || 480);
    const [x1, y1, x2, y2] = d.bbox;
    const col = d.severity === 'critical' ? '#ff3b5c' : d.severity === 'warning' ? '#ffaa00' : '#00d4ff';
    ctx.strokeStyle = col;
    ctx.lineWidth   = 2;
    ctx.strokeRect(x1*scaleX, y1*scaleY, (x2-x1)*scaleX, (y2-y1)*scaleY);
    ctx.fillStyle = col + 'cc';
    ctx.fillRect(x1*scaleX, y1*scaleY - 18, (x2-x1)*scaleX, 18);
    ctx.fillStyle = '#fff';
    ctx.font = '11px JetBrains Mono';
    ctx.fillText(`${d.label} ${(d.confidence*100).toFixed(0)}%`, x1*scaleX + 4, y1*scaleY - 4);
  });

  if (data.detections?.length) addToEventFeed({ ...data, location: 'Live Camera' });
}

function stopCamera() {
  if (cameraStream)   { cameraStream.getTracks().forEach(t => t.stop()); cameraStream = null; }
  if (wsStream)       { wsStream.close(); wsStream = null; }
  if (streamInterval) { clearInterval(streamInterval); streamInterval = null; }

  document.getElementById('cameraFeed').srcObject = null;
  document.getElementById('camStartBtn').classList.remove('hidden');
  document.getElementById('camStopBtn').classList.add('hidden');
  document.getElementById('streamStats').classList.add('hidden');
}