const API_BASE = 'http://localhost:8000/api/v1';

// ─── APP STATE ───
let currentUser = null;
let sessionId = null;
let isDemoMode = false;
let mapInitialized = false;
let leafletMap = null;
let powerlineLayer, forestLayer, hazardLayer;
let allBounds = [];

// ─── THEME ───
function initTheme() {
  const saved = localStorage.getItem('dss-theme') || 'dark';
  setTheme(saved);
}

function toggleTheme() {
  const current = document.documentElement.getAttribute('data-theme');
  setTheme(current === 'dark' ? 'light' : 'dark');
}

function setTheme(theme) {
  document.documentElement.setAttribute('data-theme', theme);
  localStorage.setItem('dss-theme', theme);
  const icon = document.getElementById('themeIcon');
  const label = document.getElementById('themeLabel');
  if (theme === 'dark') {
    icon.textContent = '☀️'; label.textContent = 'Light';
  } else {
    icon.textContent = '🌙'; label.textContent = 'Dark';
  }
  if (leafletMap) updateMapTiles(theme);
}

function updateMapTiles(theme) {
  if (!leafletMap) return;
  leafletMap.eachLayer(l => { if (l._url) leafletMap.removeLayer(l); });
  const tileUrl = theme === 'dark'
    ? 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png'
    : 'https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png';
  L.tileLayer(tileUrl, {
    attribution: '© OpenStreetMap contributors © CARTO',
    subdomains: 'abcd', maxZoom: 19
  }).addTo(leafletMap);
}

// ─── PAGE ROUTING ───
function showPage(name) {
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.getElementById('page-' + name).classList.add('active');
  window.scrollTo(0, 0);
  if (name === 'dashboard') {
    setTimeout(() => { if (!mapInitialized) { initMap(); } }, 100);
  }
}

function navigateBack() {
  if (currentUser || isDemoMode) showPage('dashboard');
  else showPage('home');
}

// ─── AUTH TAB TOGGLE ───
function switchAuthTab(name) {
  document.querySelectorAll('.auth-tab').forEach(t => t.classList.toggle('active', t.dataset.tab === name));
  document.querySelectorAll('.tab-content').forEach(c => c.classList.toggle('hidden', c.id !== 'tab-' + name));
  document.getElementById('auth-alert').style.display = 'none';
}

function showAuthAlert(msg, type) {
  const el = document.getElementById('auth-alert');
  el.className = 'alert alert-' + type;
  el.textContent = msg;
  el.style.display = 'block';
}

// ─── LOGIN ───
async function handleLogin() {
  const email = document.getElementById('login-email').value.trim();
  const password = document.getElementById('login-password').value;
  if (!email || !password) { showAuthAlert('Please fill in all fields.', 'error'); return; }

  try {
    const res = await fetch(`${API_BASE}/../../login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Login failed');

    sessionId = data.session_id;
    localStorage.setItem('dss-session', sessionId);

    const profileRes = await fetch(`${API_BASE}/../../me?session_id=${sessionId}`);
    const profile = await profileRes.json();
    currentUser = profile;
    isDemoMode = false;

    applyUserToDashboard(profile);
    showPage('dashboard');
    loadDashboardData();
  } catch (err) {
    showAuthAlert(err.message, 'error');
  }
}

// ─── SIGNUP ───
async function handleSignup() {
  const company = document.getElementById('signup-company').value.trim();
  const role = document.getElementById('signup-role').value;
  const email = document.getElementById('signup-email').value.trim();
  const password = document.getElementById('signup-password').value;

  if (!company || !role || !email || !password) { showAuthAlert('Please fill in all fields.', 'error'); return; }
  if (password.length < 6) { showAuthAlert('Password must be at least 6 characters.', 'error'); return; }

  try {
    const res = await fetch(`${API_BASE}/../../register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password, company_name: company, role })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Registration failed');

    showAuthAlert('Account created! Please sign in.', 'success');
    switchAuthTab('login');
  } catch (err) {
    showAuthAlert(err.message, 'error');
  }
}

// ─── LOGOUT ───
async function handleLogout() {
  const sid = sessionId || localStorage.getItem('dss-session');
  if (sid && !isDemoMode) {
    try { await fetch(`${API_BASE}/../../logout?session_id=${sid}`, { method: 'POST' }); } catch (e) {}
  }
  currentUser = null;
  sessionId = null;
  isDemoMode = false;
  localStorage.removeItem('dss-session');
  localStorage.removeItem('dss-demo-mode');
  showPage('home');
}

function applyUserToDashboard(user) {
  const name = user.company_name || user.email || 'User';
  document.getElementById('dash-avatar').textContent = name.charAt(0).toUpperCase();
  document.getElementById('dash-company').textContent = name;
  document.getElementById('dash-plan').textContent = user.subscription_plan || 'Free';
  document.getElementById('dash-plan').className = 'company-plan plan-' + (user.subscription_plan || 'Free');
  document.getElementById('dash-subtitle').textContent = `Real-time wildfire hazard analysis for ${name}`;
}

// ─── DEMO BYPASS ───
function bypassToDemo() {
  isDemoMode = true;
  currentUser = null;
  document.getElementById('dash-avatar').textContent = 'D';
  document.getElementById('dash-company').textContent = 'Demo Corporation';
  document.getElementById('dash-plan').textContent = 'Pro';
  document.getElementById('dash-plan').className = 'company-plan plan-Pro';
  document.getElementById('dash-subtitle').textContent = 'Demo mode — Mock data loaded';
  const banner = document.getElementById('demo-banner');
  if (banner) banner.style.display = 'flex';
  showPage('dashboard');
  loadDemoData();
}

// ─── SUBSCRIPTION ───
async function selectPlan(plan) {
  if (!currentUser && !isDemoMode) { showPage('auth'); return; }
  if (isDemoMode) { alert('Please create an account to subscribe!'); showPage('auth'); return; }
  if (plan === 'Free') { alert('You are already on the Free plan.'); return; }

  try {
    const sid = sessionId || localStorage.getItem('dss-session');
    const res = await fetch(`${API_BASE}/../../payments/create-checkout?session_id=${sid}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ plan })
    });
    const data = await res.json();
    if (data.checkout_url) window.open(data.checkout_url, '_blank');
  } catch (err) {
    alert('Could not initiate checkout. Please try again.');
  }
}

function contactEnterprise() {
  window.location.href = 'mailto:enterprise@darkstonestratum.com?subject=Enterprise Plan Inquiry';
}

function showDashSection(sec) {}

// ════════════════════════════════════════════════════
// DEMO DATA
// ════════════════════════════════════════════════════

const DEMO_FORESTS = [
  { name: "Sundarbans Reserve Forest",    density: "high",   areaHectares: 102000, geometry: { type: "Polygon", coordinates: [[[88.8,21.9],[89.2,21.9],[89.2,22.4],[88.8,22.4],[88.8,21.9]]] } },
  { name: "Western Ghats Forest Belt",    density: "high",   areaHectares: 56000,  geometry: { type: "Polygon", coordinates: [[[76.1,11.5],[76.6,11.5],[76.6,12.1],[76.1,12.1],[76.1,11.5]]] } },
  { name: "Corbett National Park Buffer", density: "medium", areaHectares: 31200,  geometry: { type: "Polygon", coordinates: [[[78.7,29.4],[79.3,29.4],[79.3,29.9],[78.7,29.9],[78.7,29.4]]] } },
  { name: "Satpura Forest Reserve",       density: "medium", areaHectares: 28900,  geometry: { type: "Polygon", coordinates: [[[77.5,22.2],[78.2,22.2],[78.2,22.7],[77.5,22.7],[77.5,22.2]]] } },
  { name: "Kanha Tiger Reserve Edge",     density: "high",   areaHectares: 19500,  geometry: { type: "Polygon", coordinates: [[[80.5,22.1],[81.0,22.1],[81.0,22.5],[80.5,22.5],[80.5,22.1]]] } },
  { name: "Rajasthan Sparse Scrublands",  density: "low",    areaHectares: 9800,   geometry: { type: "Polygon", coordinates: [[[73.5,26.0],[74.2,26.0],[74.2,26.5],[73.5,26.5],[73.5,26.0]]] } },
];

const DEMO_POWERLINES = [
  { name: "IndraGrid 765kV Trunk Line Alpha",     voltageKV: 765, companyName: "IndraGrid Power Ltd", geometry: { type: "LineString", coordinates: [[88.6,21.7],[89.0,22.1],[89.3,22.6]] } },
  { name: "IndraGrid 400kV Western Spine",        voltageKV: 400, companyName: "IndraGrid Power Ltd", geometry: { type: "LineString", coordinates: [[75.8,11.3],[76.3,11.7],[76.7,12.3]] } },
  { name: "IndraGrid 220kV Corbett Feeder",       voltageKV: 220, companyName: "IndraGrid Power Ltd", geometry: { type: "LineString", coordinates: [[78.5,29.2],[79.0,29.6],[79.5,30.1]] } },
  { name: "IndraGrid 132kV Central Link",         voltageKV: 132, companyName: "IndraGrid Power Ltd", geometry: { type: "LineString", coordinates: [[77.3,22.0],[77.9,22.4],[78.4,22.8]] } },
  { name: "IndraGrid 400kV Kanha Corridor",       voltageKV: 400, companyName: "IndraGrid Power Ltd", geometry: { type: "LineString", coordinates: [[80.3,21.9],[80.7,22.3],[81.2,22.6]] } },
  { name: "IndraGrid 66kV Rajasthan Desert Link",  voltageKV: 66,  companyName: "IndraGrid Power Ltd", geometry: { type: "LineString", coordinates: [[73.3,25.8],[73.8,26.2],[74.4,26.7]] } },
];

function computeDemoHazards(powerlines, forests) {
  const hazards = [];
  powerlines.forEach(pl => {
    forests.forEach(forest => {
      const dist = minDistanceLineToPolygon(pl.geometry.coordinates, forest.geometry.coordinates[0]);
      let riskLevel, bufferRadiusM;
      if (dist < 0.03)       { riskLevel = 'high';   bufferRadiusM = 300; }
      else if (dist < 0.06)  { riskLevel = 'medium'; bufferRadiusM = 600; }
      else if (dist < 0.10)  { riskLevel = 'low';    bufferRadiusM = 1000; }
      else return;
      const midCoord = pl.geometry.coordinates[Math.floor(pl.geometry.coordinates.length / 2)];
      const bufDeg = bufferRadiusM / 111000;
      hazards.push({
        powerlineName: pl.name, forestName: forest.name, forestDensity: forest.density,
        riskLevel, distanceToForestM: Math.round(dist * 111000), bufferRadiusM,
        areaM2: Math.round(Math.PI * bufferRadiusM * bufferRadiusM),
        geometry: { type: "Polygon", coordinates: [createCirclePolygon(midCoord[0], midCoord[1], bufDeg, 16)] }
      });
    });
  });
  return hazards;
}

function minDistanceLineToPolygon(lineCoords, polyRing) {
  let minDist = Infinity;
  lineCoords.forEach(lp => {
    polyRing.forEach(pp => {
      const d = Math.sqrt(Math.pow(lp[0]-pp[0],2) + Math.pow(lp[1]-pp[1],2));
      if (d < minDist) minDist = d;
    });
  });
  return minDist;
}

function createCirclePolygon(cx, cy, r, n) {
  const pts = [];
  for (let i = 0; i <= n; i++) {
    const angle = (2 * Math.PI * i) / n;
    pts.push([cx + r * Math.cos(angle), cy + r * Math.sin(angle)]);
  }
  return pts;
}

function loadDemoData() {
  const hazards = computeDemoHazards(DEMO_POWERLINES, DEMO_FORESTS);
  renderAll(DEMO_POWERLINES, DEMO_FORESTS, hazards);
  const elP = document.getElementById('stat-powerlines');
  const elF = document.getElementById('stat-forests');
  if (elP) elP.textContent = DEMO_POWERLINES.length;
  if (elF) elF.textContent = DEMO_FORESTS.length;
}

// ════════════════════════════════════════════════════
// REAL API DATA
// ════════════════════════════════════════════════════

async function loadDashboardData() {
  const loading = document.getElementById('map-loading');
  if (loading) loading.classList.remove('hidden');

  try {
    const sid = sessionId || localStorage.getItem('dss-session');
    if (!sid) { loadDemoData(); return; }

    const res = await fetch(`${API_BASE}/geodata/dashboard?session_id=${sid}`);
    if (!res.ok) throw new Error(`Geodata fetch failed: ${res.status}`);
    const data = await res.json();

    const powerlines = (data.powerlines || []).map(p => ({
      name: p.name, voltageKV: p.voltageKV, companyName: p.companyName, geometry: p.geometry,
    }));
    const forests = (data.forests || []).map(f => ({
      name: f.name, density: f.density, areaHectares: f.areaHectares, geometry: f.geometry,
    }));
    const hazards = (data.hazards || []).map(h => ({
      powerlineName: h.powerlineName, forestName: h.forestName, forestDensity: h.forestDensity,
      riskLevel: h.riskLevel, distanceToForestM: h.distanceToForestM,
      bufferRadiusM: h.bufferRadiusM, areaM2: h.areaM2, geometry: h.geometry,
    }));

    const stats = data.stats || {};
    const elP = document.getElementById('stat-powerlines');
    const elF = document.getElementById('stat-forests');
    if (elP) elP.textContent = stats.powerlines ?? powerlines.length;
    if (elF) elF.textContent = stats.forests ?? forests.length;

    // Fall back to demo data if user has no powerlines uploaded yet
    if (powerlines.length === 0) loadDemoData();
    else renderAll(powerlines, forests, hazards);

  } catch (err) {
    console.error('Failed to load dashboard data:', err);
    loadDemoData();
  } finally {
    if (loading) loading.classList.add('hidden');
  }
}

// ─── REFRESH HAZARDS ───
async function refreshHazards() {
  const btn = document.querySelector('.btn-refresh');
  const loading = document.getElementById('map-loading');
  const lastComputed = document.getElementById('last-computed');

  if (loading) loading.classList.remove('hidden');
  if (btn) btn.classList.add('loading');

  try {
    if (isDemoMode) {
      await new Promise(r => setTimeout(r, 800));
      loadDemoData();
    } else {
      const sid = sessionId || localStorage.getItem('dss-session');
      if (sid) {
        await fetch(`${API_BASE}/geodata/hazards/recompute?session_id=${sid}`, { method: 'POST' });
      }
      await loadDashboardData();
    }
    if (lastComputed) lastComputed.textContent = `Last computed: ${new Date().toLocaleTimeString()}`;
  } catch (err) {
    console.error('Refresh failed:', err);
  } finally {
    if (loading) loading.classList.add('hidden');
    if (btn) btn.classList.remove('loading');
  }
}

// ─── ANALYSIS API HELPERS ───
async function createSector(payload) {
  const sid = sessionId || localStorage.getItem('dss-session');
  const res = await fetch(`${API_BASE}/analysis/sectors?session_id=${sid}`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload)
  });
  return res.json();
}

async function submitAnalysisJob(sectorId) {
  const sid = sessionId || localStorage.getItem('dss-session');
  const res = await fetch(`${API_BASE}/analysis/jobs?session_id=${sid}`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ sector_id: sectorId })
  });
  return res.json();
}

async function getJobStatus(jobId) {
  const res = await fetch(`${API_BASE}/analysis/jobs/${jobId}`);
  return res.json();
}

async function getSectorRecords(sectorId) {
  const res = await fetch(`${API_BASE}/analysis/sectors/${sectorId}/records`);
  return res.json();
}

async function searchRecords(params) {
  const qs = new URLSearchParams(params).toString();
  const res = await fetch(`${API_BASE}/search?${qs}`);
  return res.json();
}

async function syncFieldUpdates(records) {
  const sid = sessionId || localStorage.getItem('dss-session');
  const res = await fetch(`${API_BASE}/sync?session_id=${sid}`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ records })
  });
  return res.json();
}

async function uploadPowerline(payload) {
  const sid = sessionId || localStorage.getItem('dss-session');
  const res = await fetch(`${API_BASE}/geodata/powerlines?session_id=${sid}`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload)
  });
  return res.json();
}

// ─── MAP ───
const RISK_COLORS = {
  high:   { fill: '#d94040', stroke: '#bf3030', opacity: 0.32 },
  medium: { fill: '#d97020', stroke: '#bf6010', opacity: 0.28 },
  low:    { fill: '#d4a020', stroke: '#b88a10', opacity: 0.22 }
};
const DENSITY_COLORS = {
  high:   { fill: '#156030', stroke: '#1a7838', opacity: 0.52 },
  medium: { fill: '#1a7838', stroke: '#20904a', opacity: 0.42 },
  low:    { fill: '#20904a', stroke: '#28b05a', opacity: 0.32 }
};

function toLatLng(coord) { return [coord[1], coord[0]]; }

function initMap() {
  if (mapInitialized) return;
  mapInitialized = true;
  const theme = document.documentElement.getAttribute('data-theme') || 'dark';
  const tileUrl = theme === 'dark'
    ? 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png'
    : 'https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png';
  leafletMap = L.map('map', { center: [20.5, 78.9], zoom: 5, zoomControl: true });
  L.tileLayer(tileUrl, { attribution: '© OpenStreetMap contributors © CARTO', subdomains: 'abcd', maxZoom: 19 }).addTo(leafletMap);
  forestLayer    = L.layerGroup().addTo(leafletMap);
  hazardLayer    = L.layerGroup().addTo(leafletMap);
  powerlineLayer = L.layerGroup().addTo(leafletMap);
}

function renderAll(powerlines, forests, hazards) {
  if (!leafletMap) return;
  powerlineLayer.clearLayers();
  forestLayer.clearLayers();
  hazardLayer.clearLayers();
  allBounds = [];
  renderForests(forests);
  renderHazards(hazards);
  renderPowerlines(powerlines);
  renderHazardTable(hazards);
  updateStatOverlay(hazards);
  fitBounds();
}

function renderPowerlines(powerlines) {
  powerlines.forEach(pl => {
    if (!pl.geometry || !pl.geometry.coordinates) return;
    const latlngs = pl.geometry.coordinates.map(toLatLng);
    const line = L.polyline(latlngs, { color: '#3a8fd4', weight: 3, opacity: 0.9 });
    line.bindPopup(`<div class="hazard-popup"><h4>⚡ ${pl.name || 'Powerline'}</h4><div class="popup-row"><span>Voltage</span><span>${pl.voltageKV || '—'} kV</span></div><div class="popup-row"><span>Company</span><span>${pl.companyName || '—'}</span></div></div>`);
    powerlineLayer.addLayer(line);
    latlngs.forEach(ll => allBounds.push(ll));
  });
}

function renderForests(forests) {
  forests.forEach(forest => {
    if (!forest.geometry) return;
    const colors = DENSITY_COLORS[forest.density] || DENSITY_COLORS.medium;
    const geom = forest.geometry;
    let polygons = geom.type === 'Polygon' ? [geom.coordinates] : geom.coordinates;
    polygons.forEach(poly => {
      const latlngs = poly.map(ring => ring.map(toLatLng));
      const layer = L.polygon(latlngs, { fillColor: colors.fill, fillOpacity: colors.opacity, color: colors.stroke, weight: 1.5, opacity: 0.8 });
      layer.bindPopup(`<div class="hazard-popup"><h4>🌲 ${forest.name || 'Forest Area'}</h4><div class="popup-row"><span>Density</span><span style="text-transform:capitalize">${forest.density}</span></div>${forest.areaHectares ? `<div class="popup-row"><span>Area</span><span>${forest.areaHectares.toLocaleString()} ha</span></div>` : ''}</div>`);
      forestLayer.addLayer(layer);
      latlngs[0].forEach(ll => allBounds.push(ll));
    });
  });
}

function renderHazards(hazards) {
  hazards.forEach(hazard => {
    if (!hazard.geometry) return;
    const colors = RISK_COLORS[hazard.riskLevel] || RISK_COLORS.low;
    const geom = hazard.geometry;
    let polygons = geom.type === 'Polygon' ? [geom.coordinates] : geom.coordinates;
    polygons.forEach(poly => {
      const latlngs = poly.map(ring => ring.map(toLatLng));
      const areaM2 = hazard.areaM2 || 0;
      const areaDisplay = areaM2 > 10000 ? `${(areaM2/10000).toFixed(1)} ha` : `${areaM2.toLocaleString()} m²`;
      const layer = L.polygon(latlngs, { fillColor: colors.fill, fillOpacity: colors.opacity, color: colors.stroke, weight: 2, opacity: 0.9, dashArray: hazard.riskLevel === 'high' ? null : '6,4' });
      layer.bindPopup(`<div class="hazard-popup"><h4>⚠️ Hazard Zone</h4><div class="popup-risk ${hazard.riskLevel}">${hazard.riskLevel.toUpperCase()} RISK</div><div class="popup-row"><span>Powerline</span><span>${hazard.powerlineName || '—'}</span></div><div class="popup-row"><span>Forest</span><span>${hazard.forestName || '—'}</span></div><div class="popup-row"><span>Density</span><span style="text-transform:capitalize">${hazard.forestDensity || '—'}</span></div><div class="popup-row"><span>Distance</span><span>${hazard.distanceToForestM || '—'} m</span></div><div class="popup-row"><span>Area</span><span>${areaDisplay}</span></div></div>`);
      layer.on('mouseover', function() { this.setStyle({ fillOpacity: Math.min(colors.opacity + 0.18, 0.65), weight: 3 }); });
      layer.on('mouseout',  function() { this.setStyle({ fillOpacity: colors.opacity, weight: 2 }); });
      hazardLayer.addLayer(layer);
      latlngs[0].forEach(ll => allBounds.push(ll));
    });
  });
}

function fitBounds() {
  if (!leafletMap) return;
  if (allBounds.length > 0) {
    try { leafletMap.fitBounds(L.latLngBounds(allBounds).pad(0.1)); }
    catch (e) { leafletMap.setView([20.5, 78.9], 5); }
  } else {
    leafletMap.setView([20.5, 78.9], 5);
  }
}

function renderHazardTable(hazards) {
  const tbody = document.getElementById('hazard-tbody');
  const noHazards = document.getElementById('no-hazards');
  const table = document.getElementById('hazard-table');
  if (!tbody) return;
  tbody.innerHTML = '';
  if (!hazards || !hazards.length) {
    if (table) table.style.display = 'none';
    if (noHazards) noHazards.classList.remove('hidden');
    return;
  }
  if (table) table.style.display = 'table';
  if (noHazards) noHazards.classList.add('hidden');
  const order = { high: 0, medium: 1, low: 2 };
  [...hazards].sort((a,b) => (order[a.riskLevel]||0) - (order[b.riskLevel]||0)).forEach(h => {
    const areaM2 = h.areaM2 || 0;
    const areaDisplay = areaM2 > 10000 ? `${(areaM2/10000).toFixed(1)} ha` : `${areaM2.toLocaleString()} m²`;
    const row = document.createElement('tr');
    row.innerHTML = `<td><span class="risk-badge-cell ${h.riskLevel}">${h.riskLevel.toUpperCase()}</span></td><td>⚡ ${h.powerlineName||'—'}</td><td>🌲 ${h.forestName||'—'}</td><td style="text-transform:capitalize">${h.forestDensity||'—'}</td><td>${h.distanceToForestM ? h.distanceToForestM+' m' : '—'}</td><td>${areaDisplay}</td>`;
    tbody.appendChild(row);
  });
}

function updateStatOverlay(hazards) {
  const high   = hazards.filter(h => h.riskLevel === 'high').length;
  const medium = hazards.filter(h => h.riskLevel === 'medium').length;
  const low    = hazards.filter(h => h.riskLevel === 'low').length;
  const set = (id, val) => { const el = document.getElementById(id); if (el) el.textContent = val; };
  set('overlay-high', high); set('overlay-medium', medium); set('overlay-low', low);
  set('stat-high', high);    set('stat-medium', medium);    set('stat-low', low);
}

// ─── SCROLL ANIMATIONS ───
function initScrollAnimations() {
  const observer = new IntersectionObserver(entries => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.style.opacity = '1';
        entry.target.style.transform = 'translateY(0)';
      }
    });
  }, { threshold: 0.1 });
  document.querySelectorAll('.step, .risk-item, .stat-card, .pricing-card').forEach(el => {
    el.style.opacity = '0';
    el.style.transform = 'translateY(20px)';
    el.style.transition = 'opacity 0.5s ease, transform 0.5s ease';
    observer.observe(el);
  });
}

// ─── INIT ───
document.addEventListener('DOMContentLoaded', () => {
  initTheme();
  initScrollAnimations();
  const savedSession = localStorage.getItem('dss-session');
  if (savedSession) sessionId = savedSession;
});