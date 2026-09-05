// dashboard.js
// Talks to the Flask API and renders: the upload form, the Leaflet map,
// the vehicle list, the alerts panel, and the per-vehicle trajectory view.

let map, markerLayer;
let camerasConfig = {};
const SPEED_LIMIT = 80; // shown for the "over limit" styling; kept in sync with cameras.json

async function fetchJSON(url, options) {
  const res = await fetch(url, options);
  if (!res.ok) throw new Error((await res.json()).error || res.statusText);
  return res.json();
}

// ---------- MAP ----------
function initMap() {
  map = L.map("map").setView([28.6139, 77.209], 12); // Delhi center
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: "&copy; OpenStreetMap contributors",
  }).addTo(map);
  markerLayer = L.layerGroup().addTo(map);
}

function plotCameraMarkers(cameras) {
  Object.entries(cameras).forEach(([id, cam]) => {
    L.circleMarker([cam.lat, cam.lon], {
      radius: 8,
      color: "#4c8bf5",
      fillColor: "#4c8bf5",
      fillOpacity: 0.6,
    })
      .bindTooltip(cam.name)
      .addTo(map);
  });
}

// ---------- CAMERAS / UPLOAD FORM ----------
async function loadCameras() {
  camerasConfig = await fetchJSON("/api/cameras");
  const select = document.getElementById("cameraSelect");
  select.innerHTML = "";
  Object.entries(camerasConfig).forEach(([id, cam]) => {
    const opt = document.createElement("option");
    opt.value = id;
    opt.textContent = cam.name;
    select.appendChild(opt);
  });
  plotCameraMarkers(camerasConfig);
  document.getElementById("statCameras").textContent = `${Object.keys(camerasConfig).length} cameras`;
}

document.getElementById("uploadForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const fileInput = document.getElementById("videoFile");
  const cameraId = document.getElementById("cameraSelect").value;
  const startTime = document.getElementById("startTime").value;
  const statusEl = document.getElementById("uploadStatus");
  const btn = document.getElementById("uploadBtn");

  if (!fileInput.files[0]) return;

  const form = new FormData();
  form.append("video", fileInput.files[0]);
  form.append("camera_id", cameraId);
  form.append("start_time", startTime);

  btn.disabled = true;
  statusEl.textContent = "Processing video... this can take a while for longer clips.";

  try {
    const result = await fetchJSON("/api/upload", { method: "POST", body: form });
    statusEl.textContent = `✅ ${result.message} — plates found: ${result.plates.join(", ") || "none"}`;
    await refreshAll();
  } catch (err) {
    statusEl.textContent = `❌ ${err.message}`;
  } finally {
    btn.disabled = false;
  }
});

// ---------- DETECTIONS / VEHICLE LIST ----------
async function loadDetections() {
  const detections = await fetchJSON("/api/detections");

  // group by plate for the table + map markers
  const byPlate = {};
  detections.forEach((d) => {
    if (!byPlate[d.plate]) byPlate[d.plate] = [];
    byPlate[d.plate].push(d);
  });

  document.getElementById("statVehicles").textContent = `${Object.keys(byPlate).length} vehicles`;

  // table
  const tbody = document.querySelector("#vehicleTable tbody");
  tbody.innerHTML = "";
  Object.entries(byPlate).forEach(([plate, dets]) => {
    dets.sort((a, b) => b.timestamp - a.timestamp);
    const cams = [...new Set(dets.map((d) => d.camera_name))];
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td><strong>${plate}</strong></td>
      <td>${new Date(dets[0].timestamp * 1000).toLocaleString()}</td>
      <td>${cams.length}</td>
    `;
    tr.addEventListener("click", () => showTrajectory(plate));
    tbody.appendChild(tr);
  });

  // markers: one small marker per detection event
  markerLayer.clearLayers();
  detections.forEach((d) => {
    L.circleMarker([d.lat, d.lon], {
      radius: 5,
      color: "#3fcf8e",
      fillColor: "#3fcf8e",
      fillOpacity: 0.8,
    })
      .bindPopup(`<b>${d.plate}</b><br>${d.camera_name}<br>${new Date(d.timestamp * 1000).toLocaleString()}`)
      .addTo(markerLayer);
  });
}

// ---------- ALERTS ----------
async function loadAlerts() {
  const alerts = await fetchJSON("/api/alerts");
  document.getElementById("statAlerts").textContent = `${alerts.length} alerts`;
  const list = document.getElementById("alertList");
  list.innerHTML = "";
  if (alerts.length === 0) {
    list.innerHTML = `<li style="border-color:#2a3450;">No alerts yet.</li>`;
    return;
  }
  alerts.forEach((a) => {
    const li = document.createElement("li");
    li.className = a.alert_type;
    li.innerHTML = `
      <span class="tag">${a.alert_type.replace("_", " ")}</span><br>
      <strong>${a.plate}</strong> — ${a.message}<br>
      <span style="color:var(--muted);font-size:11px;">${new Date(a.created_at * 1000).toLocaleString()}</span>
    `;
    list.appendChild(li);
  });
}

// ---------- TRAJECTORY ----------
async function showTrajectory(plate) {
  const data = await fetchJSON(`/api/vehicle/${encodeURIComponent(plate)}`);
  const panel = document.getElementById("trajectoryPanel");
  document.getElementById("trajPlate").textContent = data.plate;
  const legsDiv = document.getElementById("trajLegs");
  legsDiv.innerHTML = "";

  if (data.legs.length === 0) {
    legsDiv.innerHTML = `<p style="color:var(--muted)">Only seen at one camera so far — no route to show yet.</p>`;
  }

  data.legs.forEach((leg) => {
    const over = leg.speed_kmh > SPEED_LIMIT;
    const div = document.createElement("div");
    div.className = "leg";
    div.innerHTML = `
      <span>${leg.from_camera} → ${leg.to_camera}</span>
      <span>${leg.distance_km} km · ${leg.travel_time_min} min</span>
      <span class="${over ? "speed-over" : "speed-ok"}">${leg.speed_kmh} km/h</span>
    `;
    legsDiv.appendChild(div);
  });

  // draw the route on the map
  markerLayer.clearLayers();
  const latlngs = data.detections.map((d) => [d.lat, d.lon]);
  data.detections.forEach((d) => {
    L.circleMarker([d.lat, d.lon], { radius: 7, color: "#4c8bf5", fillColor: "#4c8bf5", fillOpacity: 0.9 })
      .bindPopup(`<b>${d.plate}</b><br>${d.camera_name}<br>${new Date(d.timestamp * 1000).toLocaleString()}`)
      .addTo(markerLayer);
  });
  if (latlngs.length > 1) {
    L.polyline(latlngs, { color: "#4c8bf5", weight: 3, dashArray: "6 6" }).addTo(markerLayer);
    map.fitBounds(latlngs, { padding: [40, 40] });
  }

  panel.style.display = "block";
  panel.scrollIntoView({ behavior: "smooth" });
}

document.getElementById("closeTraj").addEventListener("click", () => {
  document.getElementById("trajectoryPanel").style.display = "none";
  loadDetections(); // restore full marker set
});

// ---------- TABS ----------
document.querySelectorAll(".tab-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));
    document.querySelectorAll(".tab-content").forEach((c) => c.classList.remove("active"));
    btn.classList.add("active");
    document.getElementById(`tab-${btn.dataset.tab}`).classList.add("active");
  });
});

// ---------- INIT ----------
async function refreshAll() {
  await Promise.all([loadDetections(), loadAlerts()]);
}

(async function init() {
  initMap();
  await loadCameras();
  await refreshAll();
  setInterval(refreshAll, 15000); // auto-refresh every 15s
})();
