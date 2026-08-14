/* ================= AdminLogin — logic đăng nhập KeyForge ================= */

const ICON_XCIRCLE = `<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="m9.5 9.5 5 5"/><path d="m14.5 9.5-5 5"/></svg>`;

function togglePass(){
  const input = document.getElementById('loginPass');
  const btn = document.getElementById('passToggleBtn');
  const showing = input.type === 'text';
  input.type = showing ? 'password' : 'text';
  btn.innerHTML = showing
    ? `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-7 11-7 11 7 11 7-4 7-11 7-11-7-11-7Z"/><circle cx="12" cy="12" r="3"/></svg>`
    : `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17.94 17.94A10.94 10.94 0 0 1 12 19c-7 0-11-7-11-7a21.3 21.3 0 0 1 5.06-5.94M9.9 4.24A9.6 9.6 0 0 1 12 4c7 0 11 7 11 7a21.4 21.4 0 0 1-3.22 4.36M14.12 14.12a3 3 0 1 1-4.24-4.24"/><path d="M1 1l22 22"/></svg>`;
}

async function doLogin(){
  const base = document.getElementById('loginApiBase').value.trim();
  const key = document.getElementById('loginPass').value.trim();
  const err = document.getElementById('loginError');
  const btn = document.getElementById('loginBtn');

  if (!base || !key) {
    err.innerHTML = `${ICON_XCIRCLE}<span>Vui lòng nhập đủ Địa chỉ API và Admin Key.</span>`;
    return;
  }

  btn.disabled = true;
  const originalText = btn.textContent;
  btn.textContent = 'Đang kiểm tra...';

  try {
    const res = await fetch(base.replace(/\/+$/, '') + '/api/admin/keys', {
      headers: { 'X-Admin-Key': key }
    });
    if (!res.ok) {
      throw new Error(res.status === 401 ? 'Admin Key không đúng.' : `Lỗi HTTP ${res.status}`);
    }
    // Đăng nhập thành công -> lưu lại và chuyển sang trang dashboard
    localStorage.setItem('kf_apiBase', base);
    localStorage.setItem('kf_adminKey', key);
    window.location.href = 'index.html';
  } catch (e) {
    err.innerHTML = `${ICON_XCIRCLE}<span>Đăng nhập thất bại: ${e.message}</span>`;
    const shell = document.getElementById('loginShell');
    shell.classList.remove('shake');
    void shell.offsetWidth;
    shell.classList.add('shake');
  } finally {
    btn.disabled = false;
    btn.textContent = originalText;
  }
}

document.getElementById('loginPass').addEventListener('keydown', e=>{ if(e.key==='Enter') doLogin(); });

/* Nếu đã đăng nhập từ trước (còn lưu trong máy) -> vào thẳng dashboard, khỏi login lại */
window.addEventListener('DOMContentLoaded', ()=>{
  const savedBase = localStorage.getItem('kf_apiBase') || '';
  const savedKey = localStorage.getItem('kf_adminKey') || '';
  const baseInput = document.getElementById('loginApiBase');
  if (baseInput && savedBase) baseInput.value = savedBase;
  if (savedBase && savedKey) {
    window.location.href = 'index.html';
  }
});
