
/* ================= ICON LIBRARY (SVG code, không dùng emoji) ================= */
const ICON = {
  copy: `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="11" height="11" rx="2"/><path d="M5 15V5a2 2 0 0 1 2-2h10"/></svg>`,
  check: `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg>`,
  globe: `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M3 12h18"/><path d="M12 3c2.5 2.7 3.8 6 3.8 9s-1.3 6.3-3.8 9c-2.5-2.7-3.8-6-3.8-9s1.3-6.3 3.8-9Z"/></svg>`,
  settings: `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="21" y1="4" x2="14" y2="4"/><line x1="10" y1="4" x2="3" y2="4"/><line x1="21" y1="12" x2="12" y2="12"/><line x1="8" y1="12" x2="3" y2="12"/><line x1="21" y1="20" x2="16" y2="20"/><line x1="12" y1="20" x2="3" y2="20"/><line x1="14" y1="2" x2="14" y2="6"/><line x1="8" y1="10" x2="8" y2="14"/><line x1="16" y1="18" x2="16" y2="22"/></svg>`,
  trash: `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 7h16"/><path d="M10 11v6"/><path d="M14 11v6"/><path d="M6 7l1 13a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2l1-13"/><path d="M9 7V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v3"/></svg>`,
  checkCircle: `<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="m8.5 12.5 2.5 2.5 4.5-5"/></svg>`,
  xCircle: `<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="m9.5 9.5 5 5"/><path d="m14.5 9.5-5 5"/></svg>`
};

/* ================= STATE ================= */
let keys = [];
let currentFilter = 'all';
let activeModalKeyId = null;

// Backend đã lưu ở lần đăng nhập trước (nếu có)
let API_BASE = localStorage.getItem('kf_apiBase') || '';
let ADMIN_KEY = localStorage.getItem('kf_adminKey') || '';

const DURATION_MS = {
  '12h': 3600000 * 12, '24h': 3600000 * 24, '1d': 3600000 * 24,
  '3d': 3600000 * 24 * 3, '7d': 3600000 * 24 * 7, 'forever': null
};

/* ================= API HELPER ================= */
async function api(path, opts = {}) {
  const res = await fetch(API_BASE.replace(/\/+$/, '') + path, {
    ...opts,
    headers: {
      'Content-Type': 'application/json',
      'X-Admin-Key': ADMIN_KEY,
      ...(opts.headers || {})
    }
  });
  let data = null;
  try { data = await res.json(); } catch (e) { /* no body */ }
  if (!res.ok) {
    throw new Error((data && (data.error || data.message)) || `Lỗi HTTP ${res.status}`);
  }
  return data;
}

/* Chuyển key từ định dạng backend (main.py) sang định dạng UI dùng nội bộ */
function normalizeKey(k) {
  return {
    id: k.id,
    key: k.code,
    note: k.note || '',
    createdAt: k.created_at,
    durationMs: DURATION_MS[k.duration],
    activatedAt: k.activated_at || null,
    expiresAt: k.expires_at || null,
    lockIp: !!k.lock_ip,
    ip: k.ip || null,
    keyType: k.key_type,
    maxDevices: k.max_devices
  };
}

/* ================= AUTH GUARD ================= */
// Trang này (index.html) chỉ chứa dashboard. Việc đăng nhập nằm ở adminlogin.html.
// Nếu chưa có API_BASE/ADMIN_KEY lưu sẵn (chưa đăng nhập) -> đá về trang login.
if (!API_BASE || !ADMIN_KEY) {
  window.location.href = 'adminlogin.html';
}

function logout(){
  localStorage.removeItem('kf_apiBase');
  localStorage.removeItem('kf_adminKey');
  window.location.href = 'adminlogin.html';
}

async function refreshKeys(){
  const raw = await api('/api/admin/keys');
  keys = raw.map(normalizeKey);
  renderAll();
}

async function initDashboard(){
  try {
    const raw = await api('/api/admin/keys');
    keys = raw.map(normalizeKey);
    renderAll();
  } catch (e) {
    // Admin Key sai hoặc hết hạn phía server -> đá về login lại
    localStorage.removeItem('kf_apiBase');
    localStorage.removeItem('kf_adminKey');
    window.location.href = 'adminlogin.html';
  }
}

/* ================= CREATE ================= */
async function createKeys(){
  const note = document.getElementById('inNote').value.trim();
  const durVal = parseFloat(document.getElementById('inDuration').value) || 1;
  const unit = document.getElementById('inUnit').value; // hour/day/month
  const count = Math.min(20, Math.max(1, parseInt(document.getElementById('inCount').value) || 1));
  const lockIp = document.getElementById('inLockIp').checked;

  // UI cho chọn giờ/ngày/tháng tuỳ ý -> quy về loại duration cố định mà backend hỗ trợ
  let duration = '24h';
  if (unit === 'hour') duration = durVal <= 12 ? '12h' : '24h';
  else if (unit === 'day') duration = durVal >= 7 ? '7d' : (durVal >= 3 ? '3d' : '1d');
  else if (unit === 'month') duration = 'forever';

  try {
    await api('/api/admin/create', {
      method: 'POST',
      body: JSON.stringify({ duration, note, quantity: count, lock_ip: lockIp })
    });
    document.getElementById('inNote').value = '';
    await refreshKeys();
    toast(`Đã tạo ${count} key mới`, 'ok');
  } catch (e) {
    toast(`Tạo key thất bại: ${e.message}`, 'err');
  }
}

/* ================= STATUS LOGIC ================= */
function getStatus(k){
  if(!k.activatedAt) return 'unused';
  if(k.expiresAt && k.expiresAt < Date.now()) return 'expired';
  return 'active';
}
function timeRemaining(k){
  const status = getStatus(k);
  if(status === 'unused') return `Chưa kích hoạt · thời hạn ${k.durationMs ? formatDuration(k.durationMs) : 'vĩnh viễn'}`;
  if(status === 'expired') return 'Đã hết hạn';
  if(!k.expiresAt) return 'Vĩnh viễn';
  const ms = k.expiresAt - Date.now();
  return `Còn lại ${formatDuration(ms)}`;
}
function formatDuration(ms){
  if(ms <= 0) return '0 phút';
  const mins = Math.floor(ms/60000);
  const days = Math.floor(mins/1440);
  const hours = Math.floor((mins%1440)/60);
  const m = mins%60;
  let parts = [];
  if(days) parts.push(days+'d');
  if(hours) parts.push(hours+'h');
  if(!days && m) parts.push(m+'m');
  return parts.length ? parts.join(' ') : '<1m';
}

/* ================= RENDER ================= */
function renderAll(){
  renderStats();
  renderTable();
}
function renderStats(){
  const total = keys.length;
  const unused = keys.filter(k=>getStatus(k)==='unused').length;
  const active = keys.filter(k=>getStatus(k)==='active').length;
  const used = keys.filter(k=>getStatus(k)!=='unused').length;
  document.getElementById('statTotal').textContent = total;
  document.getElementById('statUnused').textContent = unused;
  document.getElementById('statActive').textContent = active;
  document.getElementById('statUsed').textContent = used;
}
function setFilter(f){
  currentFilter = f;
  document.querySelectorAll('.filter-chip').forEach(c=>c.classList.toggle('active', c.dataset.filter===f));
  renderTable();
}
function renderTable(){
  const search = document.getElementById('searchInput').value.trim().toLowerCase();
  let list = keys.filter(k=>{
    const matchesFilter = currentFilter==='all' || getStatus(k)===currentFilter;
    const matchesSearch = !search || k.key.toLowerCase().includes(search) || k.note.toLowerCase().includes(search);
    return matchesFilter && matchesSearch;
  });

  const body = document.getElementById('tableBody');
  document.getElementById('listCount').textContent = `${list.length} key`;
  document.getElementById('emptyState').style.display = list.length ? 'none' : 'block';
  body.innerHTML = '';

  list.forEach(k=>{
    const status = getStatus(k);
    const labelMap = { unused:'Chưa dùng', active:'Đang hoạt động', expired:'Hết hạn' };
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>
        <div class="key-cell">
          <span class="status-dot ${status}"></span>
          <div>
            <div class="key-text mono">${k.key}</div>
            <div style="font-size:11.5px;color:var(--text-faint);">${k.note || 'Không ghi chú'}</div>
          </div>
        </div>
      </td>
      <td><span class="badge ${status}">${labelMap[status]}</span></td>
      <td style="color:var(--text-dim);">${timeRemaining(k)}</td>
      <td>
        ${k.ip ? `<span class="ip-text mono">${k.ip}</span>` : `<span class="ip-text none">chưa gán</span>`}
        ${k.lockIp ? `<span class="lock-tag">🔒 IP</span>` : ''}
      </td>
      <td>
        <div class="action-group" style="justify-content:flex-end;">
          <button class="btn-icon" title="Copy key" onclick="copyKey(${k.id})">${ICON.copy}</button>
          <button class="btn-icon" title="Kiểm tra key" onclick="openCheck(${k.id})">${ICON.check}</button>
          <button class="btn-icon" title="Xoá key" style="color:var(--rose);" onclick="deleteKey(${k.id})">${ICON.trash}</button>
        </div>
      </td>
    `;
    tr.classList.add('key-enter');
    body.appendChild(tr);
  });
}

/* ================= ACTIONS ================= */
function findKey(id){ return keys.find(k=>k.id===id); }

function copyKey(id){
  const k = findKey(id);
  if(!k) return;
  navigator.clipboard.writeText(k.key).then(()=>{
    toast('Đã copy key vào clipboard', 'ok');
  }).catch(()=>{
    toast('Không thể copy — trình duyệt chặn clipboard', 'err');
  });
}

async function deleteKey(id){
  const k = findKey(id);
  if(!k) return;
  if(!confirm(`Xoá key ${k.key}? Hành động này không thể hoàn tác.`)) return;
  try {
    await api(`/api/admin/delete/${id}`, { method: 'DELETE' });
    keys = keys.filter(kk=>kk.id!==id);
    renderAll();
    toast('Đã xoá key', 'ok');
  } catch (e) {
    toast(`Xoá thất bại: ${e.message}`, 'err');
  }
}

async function openCheck(id){
  let k = findKey(id);
  if(!k) return;
  activeModalKeyId = id;
  try {
    if (!k.activatedAt) {
      const updated = await api(`/api/admin/keys/${id}/activate`, { method: 'POST' });
      k = normalizeKey(updated);
      const idx = keys.findIndex(kk=>kk.id===id);
      keys[idx] = k;
    }
  } catch (e) {
    toast(`Không thể kích hoạt: ${e.message}`, 'err');
    return;
  }
  const status = getStatus(k);
  const labelMap = {
    unused:'Chưa dùng',
    active:`${ICON.checkCircle} Đang hoạt động`,
    expired:`${ICON.xCircle} Đã hết hạn`
  };
  document.getElementById('checkModalBody').innerHTML = `
    <div class="kv-row"><span class="k">Key</span><span class="v mono">${k.key}</span></div>
    <div class="kv-row"><span class="k">Trạng thái</span><span class="v">${labelMap[status]}</span></div>
    <div class="kv-row"><span class="k">Ghi chú</span><span class="v">${k.note||'—'}</span></div>
    <div class="kv-row"><span class="k">Ngày tạo</span><span class="v">${new Date(k.createdAt).toLocaleString('vi-VN')}</span></div>
    <div class="kv-row"><span class="k">Kích hoạt lúc</span><span class="v">${k.activatedAt ? new Date(k.activatedAt).toLocaleString('vi-VN') : '—'}</span></div>
    <div class="kv-row"><span class="k">Hết hạn lúc</span><span class="v">${k.expiresAt ? new Date(k.expiresAt).toLocaleString('vi-VN') : (k.activatedAt ? 'Vĩnh viễn' : '—')}</span></div>
    <div class="kv-row"><span class="k">Khoá IP</span><span class="v">${k.lockIp ? 'Có' : 'Không'}</span></div>
    <div class="kv-row"><span class="k">IP đã gán</span><span class="v">${k.ip || 'Chưa có'}</span></div>
  `;
  document.getElementById('checkModal').classList.add('show');
  renderAll();
}

function openIpCheck(id){ switchTab('ip'); document.getElementById('ipKeySelect').value = id; renderIpTabInfo(); }
function openConfig(id){ switchTab('config'); document.getElementById('configKeySelect').value = id; renderConfigTab(); }

/* ================= TABS ================= */
function switchTab(name){
  document.querySelectorAll('.tab-btn').forEach(b=>b.classList.toggle('active', b.dataset.tab===name));
  document.querySelectorAll('.tab-content').forEach(c=>c.classList.remove('active'));
  document.getElementById('tab-'+name).classList.add('active');
  if(name==='config'){ populateKeySelects(); renderConfigTab(); }
  if(name==='ip'){ populateKeySelects(); renderIpTabInfo(); renderIpRegistry(); }
}

function populateKeySelects(){
  const options = keys.length
    ? keys.map(k=>`<option value="${k.id}">${k.key} — ${k.note || 'Không ghi chú'}</option>`).join('')
    : `<option value="">Chưa có key nào</option>`;
  ['configKeySelect','ipKeySelect'].forEach(selId=>{
    const sel = document.getElementById(selId);
    const prev = sel.value;
    sel.innerHTML = options;
    if(keys.some(k=>String(k.id)===prev)) sel.value = prev;
  });
}

/* ---------- GET CONFIG TAB ---------- */
async function renderConfigTab(){
  const box = document.getElementById('configTabBox');
  const sel = document.getElementById('configKeySelect');
  const id = parseInt(sel.value);
  const k = findKey(id);
  if(!k){ box.innerHTML = `<div class="config-empty">Chọn một key ở trên để lấy cấu hình.</div>`; return; }
  box.textContent = 'Đang tải...';
  try {
    const config = await api(`/api/admin/keys/${id}/config`);
    box.textContent = JSON.stringify(config, null, 2);
  } catch (e) {
    box.innerHTML = `<div class="config-empty">Lỗi tải config: ${e.message}</div>`;
  }
}
function copyConfigTab(){
  const box = document.getElementById('configTabBox');
  const text = box.textContent.trim();
  if(!text || box.querySelector('.config-empty')){ toast('Chưa chọn key để lấy config', 'err'); return; }
  navigator.clipboard.writeText(text).then(()=>toast('Đã copy config', 'ok'))
    .catch(()=>toast('Không thể copy config', 'err'));
}

/* ---------- CHECK IP TAB ---------- */
function renderIpTabInfo(){
  const sel = document.getElementById('ipKeySelect');
  const k = findKey(parseInt(sel.value));
  document.getElementById('ipTabResult').innerHTML = '';
  document.getElementById('ipTabInput').value = '';
  document.getElementById('ipTabLock').textContent = k ? (k.lockIp ? 'Có' : 'Không') : '—';
  document.getElementById('ipTabCurrent').textContent = k ? (k.ip || 'Chưa gán') : '—';
}
async function runIpCheckTab(){
  const sel = document.getElementById('ipKeySelect');
  const id = parseInt(sel.value);
  const k = findKey(id);
  const ipVal = document.getElementById('ipTabInput').value.trim();
  const resultEl = document.getElementById('ipTabResult');
  if(!k){ resultEl.innerHTML = `<span style="color:var(--rose)">Vui lòng chọn key.</span>`; return; }
  if(!ipVal){ resultEl.innerHTML = `<span style="color:var(--rose)">Vui lòng nhập địa chỉ IP.</span>`; return; }

  try {
    const res = await api(`/api/admin/keys/${id}/check-ip`, {
      method: 'POST',
      body: JSON.stringify({ ip: ipVal })
    });
    const colorMap = { no_lock: 'var(--amber)', assigned: 'var(--emerald)', match: 'var(--emerald)', mismatch: 'var(--rose)' };
    const iconMap = { no_lock: ICON.xCircle, assigned: ICON.checkCircle, match: ICON.checkCircle, mismatch: ICON.xCircle };
    resultEl.innerHTML = `<span style="display:inline-flex;align-items:center;gap:6px;color:${colorMap[res.result]}">${iconMap[res.result]} ${res.message}</span>`;
    k.ip = res.ip;
    document.getElementById('ipTabCurrent').textContent = k.ip || 'Chưa gán';
    renderAll();
  } catch (e) {
    resultEl.innerHTML = `<span style="color:var(--rose)">Lỗi: ${e.message}</span>`;
  }
}
function renderIpRegistry(){
  const body = document.getElementById('ipRegistryBody');
  document.getElementById('ipRegistryCount').textContent = `${keys.length} key`;
  if(!keys.length){ body.innerHTML = `<div class="config-empty">Chưa có key nào.</div>`; return; }
  body.innerHTML = keys.map(k=>`
    <div class="ip-registry-row">
      <div class="rk">
        <span class="mono" style="color:var(--text);">${k.key}</span>
        <span style="color:var(--text-faint);font-size:11px;">${k.note || 'Không ghi chú'}</span>
      </div>
      <div style="text-align:right;">
        <div class="mono" style="color:${k.ip ? 'var(--text)' : 'var(--text-faint)'};">${k.ip || 'chưa gán'}</div>
        <div style="font-size:10.5px;color:${k.lockIp ? 'var(--violet)' : 'var(--text-faint)'};">${k.lockIp ? 'Khoá IP' : 'Không khoá'}</div>
      </div>
    </div>
  `).join('');
}

function closeModal(id){
  document.getElementById(id).classList.remove('show');
}

/* ================= TOAST ================= */
function toast(msg, type=''){
  const host = document.getElementById('toastHost');
  const el = document.createElement('div');
  el.className = `toast ${type}`;
  el.textContent = msg;
  host.appendChild(el);
  setTimeout(()=>{ el.style.opacity='0'; el.style.transition='opacity .3s'; setTimeout(()=>el.remove(),300); }, 2600);
}

/* ================= AUTO REFRESH ================= */
setInterval(()=>{ refreshKeys().catch(()=>{}); }, 30000);

/* Đóng modal khi click nền */
document.querySelectorAll('.modal-overlay').forEach(ov=>{
  ov.addEventListener('click', e=>{ if(e.target===ov) ov.classList.remove('show'); });
});

/* Tải danh sách key ngay khi vào trang (đã đăng nhập ở adminlogin.html trước đó) */
window.addEventListener('DOMContentLoaded', initDashboard);
