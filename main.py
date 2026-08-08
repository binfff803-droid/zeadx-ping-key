from flask import Flask, request, jsonify, redirect, session
from flask_cors import CORS
import json
import os
import random
import string
import time
import requests
from datetime import datetime
from urllib.parse import quote

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "zeadx-ping-key-secret-2026-doi-neu-can")
CORS(app)

# QUAN TRỌNG: repo GitHub của bạn đang để Public, ai cũng xem được thông tin dưới đây.
# Nên đổi tài khoản/mật khẩu định kỳ, hoặc chuyển repo sang Private nếu có thể.
ADMIN_USERNAME = "Sonhuyzdx"
ADMIN_PASSWORD = "zeadxvn10101"

KEY_FILE = "keys.json"

def login_required(f):
    from functools import wraps
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("is_admin"):
            return jsonify({"error": "Chưa đăng nhập"}), 401
        return f(*args, **kwargs)
    return wrapper
DAILY_LIMIT = 500
LINK4M_TOKEN = "69902dcc482df052bb6c2347"
LINK4M_API = "https://link4m.co/api-shorten/v2"
# QUAN TRỌNG: Link4m chỉ chấp nhận rút gọn các URL truy cập công khai được.
# Nếu để trống, app sẽ tự lấy host từ request (vd: http://127.0.0.1:5005) —
# nhưng địa chỉ này KHÔNG hoạt động với Link4m vì nó là local/private.
# Hãy chạy ngrok (hoặc cloudflared) để có domain public, ví dụ:
#   ngrok http 5005
# rồi dán URL https://xxxx.ngrok-free.app vào đây (không có dấu / ở cuối).
PUBLIC_BASE_URL = ""  # Để trống khi deploy lên Render — sẽ tự lấy domain Render.

def load_keys():
    if os.path.exists(KEY_FILE):
        with open(KEY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_keys(keys):
    with open(KEY_FILE, "w", encoding="utf-8") as f:
        json.dump(keys, f, indent=2, ensure_ascii=False)

def gen_key_code():
    def seg():
        return ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
    return f"ZEADX-{seg()}-{seg()}-{seg()}"

def count_created_today(keys):
    today = datetime.now().date()
    cnt = 0
    for k in keys:
        created = datetime.fromtimestamp(k["created_at"] / 1000).date()
        if created == today:
            cnt += 1
    return cnt

def create_new_key(duration_type):
    keys = load_keys()
    if count_created_today(keys) >= DAILY_LIMIT:
        return None, "Đã đạt giới hạn 100 key/ngày"
    duration_map = {
        "12h": 12 * 60 * 60 * 1000,
        "24h": 24 * 60 * 60 * 1000,
        "1d": 24 * 60 * 60 * 1000,
        "3d": 3 * 24 * 60 * 60 * 1000,
        "7d": 7 * 24 * 60 * 60 * 1000,
        "forever": None
    }
    ms = duration_map.get(duration_type)
    now = time.time() * 1000
    expires_at = now + ms if ms is not None else None
    new_key = {
        "id": int(time.time() * 1000) + random.randint(1, 10000),
        "code": gen_key_code(),
        "duration": duration_type,
        "created_at": now,
        "expires_at": expires_at,
        "used": False
    }
    keys.insert(0, new_key)
    save_keys(keys)
    return new_key, None

def shorten_url(long_url):
    """Gọi API Link4m để rút gọn URL, trả về short URL hoặc None nếu lỗi"""
    try:
        params = {
            "api": LINK4M_TOKEN,
            "url": long_url
        }
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "application/json"
        }
        resp = requests.get(LINK4M_API, params=params, headers=headers, timeout=10, allow_redirects=False)
        if resp.status_code in (301, 302, 303, 307, 308):
            print("Link4m redirect (thường do URL đích không public/không hợp lệ). "
                  "Location:", resp.headers.get("Location"))
            return None
        try:
            data = resp.json()
        except ValueError:
            print("Link4m không trả JSON. HTTP status:", resp.status_code)
            print("Nội dung trả về (300 ký tự đầu):", resp.text[:300])
            return None
        if data.get("status") == "success":
            return data.get("shortenedUrl")
        else:
            print("Link4m trả lỗi:", data.get("message", data))
            return None
    except Exception as e:
        print("Lỗi khi gọi Link4m:", e)
        return None

# ---- Route chuyển hướng trung gian cho 24H ----
@app.route("/redirect/<key>")
def redirect_link(key):
    link2 = request.args.get("to")
    if link2:
        return redirect(link2)
    else:
        return "Link không hợp lệ hoặc đã hết hạn", 404

# ---- Giao diện chính ----
@app.route("/")
def index():
    return '''
    <!DOCTYPE html>
    <html lang="vi">
    <head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Zeadx Ping Key</title>
    <style>
      :root{
        --bg-1:#150a24;
        --bg-2:#1c0f33;
        --violet:#8b5cf6;
        --pink:#ec4899;
        --card-border:rgba(139,92,246,0.25);
        --text-dim:#8b93a7;
      }
      *{box-sizing:border-box;}
      html,body{
        margin:0; padding:0; min-height:100vh;
        background:radial-gradient(circle at 15% 8%, #2a1550 0%, transparent 45%),
                  radial-gradient(circle at 90% 15%, #34104f 0%, transparent 50%),
                  radial-gradient(circle at 50% 100%, #170a2e 0%, transparent 60%),
                  linear-gradient(180deg,var(--bg-1) 0%, var(--bg-2) 100%);
        font-family: 'Segoe UI', sans-serif; color:#fff; overflow-x:hidden;
      }
      .dot{ position:fixed; border-radius:50%; pointer-events:none; opacity:0; filter:blur(0.3px); animation: floatUp linear infinite; }
      @keyframes floatUp{
        0%{ transform:translateY(0) translateX(0) scale(0.6); opacity:0; }
        8%{ opacity:var(--maxop,0.9); }
        50%{ transform:translateY(var(--midY,-50vh)) translateX(var(--driftX,10px)) scale(1); }
        92%{ opacity:var(--maxop,0.9); }
        100%{ transform:translateY(var(--endY,-100vh)) translateX(calc(var(--driftX,10px) * 2)) scale(0.5); opacity:0; }
      }
      .container{ max-width:480px; margin:0 auto; padding:64px 22px; text-align:center; position:relative; z-index:2; }
      .navbar{ position:fixed; top:0; left:0; z-index:50; padding:16px; }
      .hamburger-btn{ width:44px; height:44px; border-radius:12px; background:rgba(17,24,39,0.9); border:1px solid var(--card-border); display:flex; align-items:center; justify-content:center; cursor:pointer; backdrop-filter:blur(8px); }
      .hamburger-btn svg{ width:20px; height:20px; }
      .nav-menu{ position:fixed; top:64px; left:16px; z-index:60; width:220px; background:rgba(17,24,39,0.97); border:1px solid var(--card-border); border-radius:16px; padding:8px; backdrop-filter:blur(10px); box-shadow:0 25px 60px -20px rgba(139,92,246,0.5); display:none; flex-direction:column; gap:2px; }
      .nav-menu.show{ display:flex; }
      .nav-item{ display:flex; align-items:center; gap:10px; padding:12px 14px; border-radius:10px; text-decoration:none; color:#e5e7eb; font-size:14.5px; font-weight:600; text-align:left; background:none; border:none; cursor:pointer; }
      .nav-item:hover, .nav-item.active-nav{ background:linear-gradient(90deg,rgba(139,92,246,0.25),rgba(236,72,153,0.18)); }
      .nav-item .nav-ic{ font-size:16px; }
      .card{ background:rgba(17,24,39,0.85); border:1px solid var(--card-border); border-radius:22px; padding:36px 24px; backdrop-filter:blur(8px); box-shadow:0 25px 60px -25px rgba(139,92,246,0.4); }
      .music-bar{ width:100%; margin-bottom:22px; accent-color:#8b5cf6; border-radius:12px; height:40px; background:rgba(139,92,246,0.08); border:1px solid rgba(139,92,246,0.35); }
      .music-bar::-webkit-media-controls-panel{ background-color:#1c0f33; }
      .music-bar::-webkit-media-controls-play-button,
      .music-bar::-webkit-media-controls-mute-button{ filter:invert(45%) sepia(90%) saturate(1000%) hue-rotate(230deg); }
      .music-bar::-webkit-media-controls-current-time-display,
      .music-bar::-webkit-media-controls-time-remaining-display{ color:#ec4899; }
      h1{ font-size:28px; font-weight:800; margin:0 0 12px; background:linear-gradient(90deg,#8b5cf6,#ec4899); -webkit-background-clip:text; background-clip:text; color:transparent; }
      .subtitle{ color:var(--text-dim); font-size:14.5px; margin-bottom:28px; }
      .field-label{ text-align:left; font-size:12px; font-weight:700; letter-spacing:1px; color:#93a0bb; margin-bottom:10px; }
      .static-field{ background:rgba(8,12,22,0.75); border:1.5px solid rgba(139,92,246,0.35); border-radius:14px; padding:16px; font-size:15px; color:#fff; text-align:left; margin-bottom:24px; }
      .duration-row{ display:flex; gap:12px; margin-bottom:24px; }
      .duration-opt{ flex:1; background:rgba(8,12,22,0.7); border:1.5px solid rgba(139,92,246,0.3); border-radius:16px; padding:20px 10px; text-align:center; cursor:pointer; transition:all .2s; }
      .duration-opt .hh{ font-size:26px; font-weight:800; color:#fff; margin-bottom:8px; }
      .duration-opt .sub{ font-size:12.5px; color:var(--text-dim); }
      .duration-opt.active{ border-color:var(--pink); background:rgba(236,72,153,0.14); box-shadow:0 0 22px -6px rgba(236,72,153,0.55); }
      .badge{ font-size:10.5px; font-weight:800; padding:3px 8px; border-radius:8px; }
      .badge-free{ background:rgba(52,211,153,0.15); color:#34d399; }
      .badge-custom{ background:rgba(139,92,246,0.2); color:#a78bfa; }
      .btn-primary{ width:100%; border:none; border-radius:14px; padding:17px; font-size:15.5px; font-weight:800; color:#fff; cursor:pointer; background:linear-gradient(90deg,#8b5cf6,#ec4899); box-shadow:0 12px 28px -10px rgba(236,72,153,0.55); transition:transform .15s; display:flex; align-items:center; justify-content:center; gap:10px; }
      .btn-primary:active{ transform:scale(0.98); }
      .btn-primary:disabled{ opacity:0.75; cursor:not-allowed; }
      .spinner{ width:18px; height:18px; border:3px solid rgba(255,255,255,0.35); border-top-color:#fff; border-radius:50%; animation:spin .7s linear infinite; display:none; }
      .spinner.show{ display:inline-block; }
      @keyframes spin{ to{ transform:rotate(360deg); } }
      .footer-note{ margin-top:28px; color:var(--text-dim); font-size:13.5px; }
      .contact-card{ max-width:460px; width:100%; margin:22px auto 0; background:rgba(17,24,39,0.85); border:1px solid var(--card-border); border-radius:22px; padding:24px 20px; backdrop-filter:blur(8px); box-shadow:0 25px 60px -25px rgba(139,92,246,0.35); }
      .contact-title{ display:flex; align-items:center; gap:8px; font-weight:800; font-size:15px; color:#fff; margin-bottom:16px; }
      .contact-title span.icon{ color:#ec4899; }
      .contact-link{ display:flex; align-items:center; justify-content:space-between; padding:14px 16px; border-radius:14px; margin-bottom:10px; text-decoration:none; background:linear-gradient(90deg,rgba(139,92,246,0.18),rgba(236,72,153,0.12)); border:1px solid rgba(139,92,246,0.3); transition:transform .15s, box-shadow .15s, border-color .15s; }
      .contact-link:active{ transform:scale(0.97); box-shadow:0 8px 24px -10px rgba(236,72,153,0.5); border-color:rgba(236,72,153,0.55); }
      .contact-link:last-child{ margin-bottom:0; }
      .contact-icon svg{ width:20px; height:20px; }
      .contact-left{ display:flex; align-items:center; gap:12px; }
      .contact-icon{ width:36px; height:36px; border-radius:10px; display:flex; align-items:center; justify-content:center; font-size:15px; font-weight:800; color:#fff; flex-shrink:0; }
      .contact-name{ font-size:12px; color:var(--text-dim); text-transform:uppercase; letter-spacing:.5px; }
      .contact-handle{ font-size:14.5px; font-weight:700; color:#fff; }
      .contact-arrow{ color:var(--text-dim); font-size:18px; }
      .zalo-numbers{ color:#f0abfc; font-weight:700; }
      .copyright{ margin-top:30px; font-size:11.5px; color:#4a5468; }
    </style>
    </head>
    <body>
    <div class="navbar">
      <button class="hamburger-btn" id="hamburgerBtn" aria-label="Menu">
        <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M3 6h18M3 12h18M3 18h18" stroke="#fff" stroke-width="2" stroke-linecap="round"/></svg>
      </button>
      <div class="nav-menu" id="navMenu">
        <a class="nav-item active-nav" href="/"><span class="nav-ic">&#127968;</span> Trang Chủ</a>
        <a class="nav-item" href="/tim-nhac"><span class="nav-ic">&#127925;</span> Tìm Nhạc</a>
        <a class="nav-item" href="/"><span class="nav-ic">&#128273;</span> Lấy Key</a>
        <a class="nav-item" href="/tra-cuu-key"><span class="nav-ic">&#128269;</span> Tra Cứu Key</a>
        <a class="nav-item" href="/admin/login"><span class="nav-ic">&#128100;</span> Admin Login</a>
      </div>
    </div>
    <script>
      (function(){ var btn=document.getElementById('hamburgerBtn'); var menu=document.getElementById('navMenu'); if(!btn||!menu) return; btn.addEventListener('click', function(e){ e.stopPropagation(); menu.classList.toggle('show'); }); document.addEventListener('click', function(e){ if(!menu.contains(e.target) && e.target!==btn){ menu.classList.remove('show'); } }); })();
    </script>
    <div class="container">
      <div class="card">
        <audio class="music-bar" id="genSound" src="/static/key-sound.mp3" controls loop preload="auto"></audio>
        <h1>Zeadx Ping — Lấy Key</h1>
        <div class="subtitle">Hệ thống vượt link nhận Key tự động</div>
        <div class="field-label">CHỌN WEB VƯỢT MÃ:</div>
        <div class="static-field">Link4m.co</div>
        <div class="field-label">CHỌN THỜI GIAN GÓI:</div>
        <div class="duration-row">
          <div class="duration-opt active" data-hours="12">
            <div class="hh">12H</div>
            <div class="sub">Vượt 1 lần <span class="badge badge-free">FREE</span></div>
          </div>
          <div class="duration-opt" data-hours="24">
            <div class="hh">24H</div>
            <div class="sub">Vượt 2 lần <span class="badge badge-custom">CUSTOM</span></div>
          </div>
        </div>
        <button class="btn-primary" id="genBtn"><span class="spinner" id="genSpinner"></span><span id="genBtnLabel">TẠO LINK 12H</span></button>
      </div>
      <div class="contact-card">
        <div class="contact-title"><span class="icon">&#128279;</span> KẾT NỐI VỚI ADMIN</div>
        <a class="contact-link" href="https://zalo.me/0938738602" target="_blank" rel="noopener">
          <div class="contact-left">
            <div class="contact-icon" style="background:#0068ff;">
              <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M4 4h16v11.5a2 2 0 0 1-2 2H9.5L5 21.5V17.5H6a2 2 0 0 1-2-2V4Z" fill="#fff"/><text x="12" y="13.5" text-anchor="middle" font-size="6.5" font-weight="800" fill="#0068ff" font-family="Arial">Zalo</text></svg>
            </div>
            <div>
              <div class="contact-name">Zalo</div>
              <div class="contact-handle">0938738602</div>
            </div>
          </div>
          <span class="contact-arrow">&#8250;</span>
        </a>
        <a class="contact-link" href="https://zalo.me/0961291657" target="_blank" rel="noopener">
          <div class="contact-left">
            <div class="contact-icon" style="background:#0068ff;">
              <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M4 4h16v11.5a2 2 0 0 1-2 2H9.5L5 21.5V17.5H6a2 2 0 0 1-2-2V4Z" fill="#fff"/><text x="12" y="13.5" text-anchor="middle" font-size="6.5" font-weight="800" fill="#0068ff" font-family="Arial">Zalo</text></svg>
            </div>
            <div>
              <div class="contact-name">Zalo</div>
              <div class="contact-handle">0961291657</div>
            </div>
          </div>
          <span class="contact-arrow">&#8250;</span>
        </a>
        <a class="contact-link" href="https://www.tiktok.com/@binmodvn" target="_blank" rel="noopener">
          <div class="contact-left">
            <div class="contact-icon" style="background:#000;">
              <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M16.5 3c.4 2.2 1.9 3.7 4 4v3c-1.5 0-2.9-.4-4-1.2v6.7c0 3.1-2.5 5.5-5.6 5.5A5.6 5.6 0 0 1 5.4 15.4c0-3.1 2.5-5.5 5.6-5.5.4 0 .8 0 1.1.1v3.1a2.5 2.5 0 1 0 1.9 2.4V3h2.5Z" fill="#fff"/></svg>
            </div>
            <div>
              <div class="contact-name">TikTok</div>
              <div class="contact-handle">@binmodvn</div>
            </div>
          </div>
          <span class="contact-arrow">&#8250;</span>
        </a>
        <a class="contact-link" href="https://www.tiktok.com/@zeadxvncheat101" target="_blank" rel="noopener">
          <div class="contact-left">
            <div class="contact-icon" style="background:#000;">
              <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M16.5 3c.4 2.2 1.9 3.7 4 4v3c-1.5 0-2.9-.4-4-1.2v6.7c0 3.1-2.5 5.5-5.6 5.5A5.6 5.6 0 0 1 5.4 15.4c0-3.1 2.5-5.5 5.6-5.5.4 0 .8 0 1.1.1v3.1a2.5 2.5 0 1 0 1.9 2.4V3h2.5Z" fill="#fff"/></svg>
            </div>
            <div>
              <div class="contact-name">TikTok</div>
              <div class="contact-handle">@zeadxvncheat101</div>
            </div>
          </div>
          <span class="contact-arrow">&#8250;</span>
        </a>
      </div>
      <div class="copyright">© 2026 ZEADX PING KEY | All Rights Reserved.</div>
    </div>
    <script>
      const colors = [{c:'#ffffff',glow:'rgba(255,255,255,0.9)'},{c:'#ff4d6d',glow:'rgba(255,77,109,0.9)'},{c:'#38bdf8',glow:'rgba(56,189,248,0.9)'}];
      for(let i=0;i<45;i++){ const dot=document.createElement('div'); dot.className='dot'; const pal=colors[i%colors.length]; const size=Math.random()*3.5+1.5; dot.style.left=Math.random()*100+'vw'; dot.style.bottom='-5vh'; dot.style.width=size+'px'; dot.style.height=size+'px'; dot.style.background=pal.c; dot.style.boxShadow=`0 0 ${size*3}px ${pal.glow}`; dot.style.setProperty('--maxop',(Math.random()*0.5+0.4).toFixed(2)); dot.style.setProperty('--driftX',(Math.random()*60-30)+'px'); dot.style.setProperty('--midY','-55vh'); dot.style.setProperty('--endY','-115vh'); dot.style.animationDuration=(Math.random()*10+9)+'s'; dot.style.animationDelay=(Math.random()*14)+'s'; document.body.appendChild(dot); }
      const opts=document.querySelectorAll('.duration-opt'); const genBtn=document.getElementById('genBtn'); const genSpinner=document.getElementById('genSpinner'); const genBtnLabel=document.getElementById('genBtnLabel'); const genSound=document.getElementById('genSound');
      opts.forEach(opt=>opt.addEventListener('click',()=>{ opts.forEach(o=>o.classList.remove('active')); opt.classList.add('active'); genBtnLabel.textContent='TẠO LINK '+opt.querySelector('.hh').textContent; }));
      function setLoading(isLoading){ genBtn.disabled=isLoading; genSpinner.classList.toggle('show',isLoading); genBtnLabel.textContent=isLoading?'Đang tải...':('TẠO LINK '+(document.querySelector('.duration-opt.active').querySelector('.hh').textContent)); }
      genBtn.addEventListener('click',function(){ try{ genSound.currentTime=0; genSound.play(); }catch(e){} const active=document.querySelector('.duration-opt.active'); const hours=active?active.dataset.hours:'12'; setLoading(true); fetch('/api/generate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({hours:hours})}).then(res=>res.json()).then(data=>{ if(data.error){ setLoading(false); alert(data.error); return; } if(data.short_url){ window.location.href=data.short_url; } else { setLoading(false); alert('Không thể tạo link, vui lòng thử lại'); } }).catch(err=>{ setLoading(false); alert('Lỗi kết nối đến server: '+err); }); });
    </script>
    </body>
    </html>
    '''

# ---- Trang hiển thị key ----
@app.route("/generate")
def show_key():
    key = request.args.get('key', 'ZEADX-XXXX-XXXX-XXXX')
    duration = request.args.get('duration', '12H')
    return f'''
    <!DOCTYPE html>
    <html lang="vi">
    <head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Zeadx Ping — Đã Tạo Key</title>
    <style>
      :root{{--bg-1:#150a24;--bg-2:#1c0f33;--violet:#8b5cf6;--pink:#ec4899;--card-border:rgba(139,92,246,0.25);--text-dim:#8b93a7;--green:#34d399;}}
      *{{box-sizing:border-box;}}
      html,body{{margin:0;padding:0;min-height:100vh;background:radial-gradient(circle at 15% 8%,#2a1550 0%,transparent 45%),radial-gradient(circle at 90% 15%,#34104f 0%,transparent 50%),radial-gradient(circle at 50% 100%,#170a2e 0%,transparent 60%),linear-gradient(180deg,var(--bg-1) 0%,var(--bg-2) 100%);font-family:'Segoe UI',sans-serif;color:#fff;display:flex;align-items:center;justify-content:center;min-height:100vh;}}
      .card{{max-width:480px;width:100%;background:rgba(17,24,39,0.85);border:1px solid var(--card-border);border-radius:22px;padding:44px 26px;backdrop-filter:blur(8px);text-align:center;}}
      .check-wrap{{width:96px;height:96px;margin:0 auto 24px;border-radius:50%;background:radial-gradient(circle at 50% 40%,rgba(52,211,153,0.25) 0%,transparent 70%);display:flex;align-items:center;justify-content:center;box-shadow:0 0 0 1px rgba(52,211,153,0.35),0 0 40px 6px rgba(52,211,153,0.35);}}
      .check-wrap svg{{width:46px;height:46px;}}
      h1{{font-size:24px;font-weight:800;background:linear-gradient(90deg,#8b5cf6,#ec4899);-webkit-background-clip:text;background-clip:text;color:transparent;}}
      .subtitle{{color:var(--text-dim);font-size:14.5px;margin-bottom:20px;}}
      .key-box{{background:rgba(8,12,22,0.75);border:1.5px solid rgba(139,92,246,0.4);border-radius:16px;padding:18px 16px;display:flex;align-items:center;justify-content:space-between;gap:10px;}}
      .key-code{{font-family:'Courier New',monospace;font-size:16px;font-weight:800;color:#fff;letter-spacing:1px;word-break:break-all;text-align:left;}}
      .copy-btn{{border:none;border-radius:11px;padding:10px 14px;font-size:12.5px;font-weight:800;color:#fff;cursor:pointer;background:linear-gradient(90deg,#8b5cf6,#ec4899);box-shadow:0 8px 20px -8px rgba(236,72,153,0.55);white-space:nowrap;}}
      .copy-btn.copied{{background:linear-gradient(90deg,#22c55e,#34d399);}}
      .key-info-row{{display:flex;justify-content:space-between;margin-top:16px;font-size:12px;color:var(--text-dim);}}
      .key-info-row .val{{color:#c4b5fd;font-weight:700;}}
      .btn-primary{{width:100%;border:none;border-radius:14px;padding:16px;font-size:15px;font-weight:800;color:#fff;cursor:pointer;margin-top:24px;background:linear-gradient(90deg,#8b5cf6,#ec4899);box-shadow:0 12px 28px -10px rgba(236,72,153,0.55);}}
      .back-link{{margin-top:16px;font-size:12.5px;color:#8b93a7;cursor:pointer;}}
      .back-link:hover{{color:#f0abfc;}}
      .footer-note{{margin-top:28px;color:var(--text-dim);font-size:13.5px;}}
      .zalo-numbers{{color:#f0abfc;font-weight:700;}}
      .copyright{{margin-top:30px;font-size:11.5px;color:#4a5468;}}
    </style>
    </head>
    <body>
    <div class="card">
      <div class="check-wrap"><svg viewBox="0 0 24 24" fill="none"><path d="M20 6L9 17l-5-5" stroke="#34d399" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/></svg></div>
      <h1>Hệ Thống Đã Tạo Xong Key</h1>
      <div class="subtitle">Key của bạn đã sẵn sàng, hãy sao chép và sử dụng ngay</div>
      <div class="key-box">
        <div class="key-code" id="keyCode">{key}</div>
        <button class="copy-btn" id="copyBtn">📋 Copy</button>
      </div>
      <div class="key-info-row">
        <span>Thời hạn: <span class="val">{duration}</span></span>
        <span>Trạng thái: <span class="val" style="color:#34d399">Chưa dùng</span></span>
      </div>
      <button class="btn-primary" onclick="location.href='/'">TẠO KEY MỚI</button>
      <div class="back-link" onclick="location.href='/'">← Quay lại trang lấy Key</div>
      <div class="footer-note">Mua Key — Inbox Zalo: <span class="zalo-numbers">0961291657</span> hoặc <span class="zalo-numbers">0938738602</span></div>
      <div class="copyright">© 2026 ZEADX PING KEY | All Rights Reserved.</div>
    </div>
    <script>
      document.getElementById('copyBtn').addEventListener('click', function() {{
        const code = document.getElementById('keyCode').textContent;
        const btn = this;
        if (navigator.clipboard && navigator.clipboard.writeText) {{
          navigator.clipboard.writeText(code).then(() => {{
            btn.textContent = '✓ Đã Copy';
            btn.classList.add('copied');
            setTimeout(() => {{ btn.textContent = '📋 Copy'; btn.classList.remove('copied'); }}, 1500);
          }}).catch(() => fallbackCopy(code));
        }} else {{
          fallbackCopy(code);
          btn.textContent = '✓ Đã Copy';
          btn.classList.add('copied');
          setTimeout(() => {{ btn.textContent = '📋 Copy'; btn.classList.remove('copied'); }}, 1500);
        }}
      }});
      function fallbackCopy(text) {{
        const ta = document.createElement('textarea');
        ta.value = text;
        ta.style.position='fixed'; ta.style.opacity='0';
        document.body.appendChild(ta);
        ta.select();
        try{{ document.execCommand('copy'); }}catch(e){{}}
        document.body.removeChild(ta);
      }}
    </script>
    </body>
    </html>
    '''

# ---- API tạo key và link vượt ----
@app.route("/api/generate", methods=["POST"])
def api_generate():
    data = request.get_json()
    hours = data.get("hours", "12")
    duration_type = "12h" if hours == "12" else "24h"

    # Tạo key mới
    key_obj, err = create_new_key(duration_type)
    if err:
        return jsonify({"error": err}), 400

    key = key_obj["code"]
    duration = duration_type
    # Ưu tiên dùng PUBLIC_BASE_URL (vd: domain ngrok/local tunnel) nếu đã cấu hình,
    # nếu không thì tự lấy từ request (đúng khi deploy trên Render vì Render có domain public).
    if PUBLIC_BASE_URL:
        host = PUBLIC_BASE_URL.rstrip('/')
    else:
        host = request.host_url.rstrip('/')
        # Render chạy sau proxy HTTPS nhưng request.host_url có thể trả về http:// —
        # ép về https để link không bị lỗi mixed-content.
        if host.startswith("http://") and request.headers.get("X-Forwarded-Proto") == "https":
            host = "https://" + host[len("http://"):]
    # URL đích: trang generate
    target_url = f"{host}/generate?key={key}&duration={duration}"

    # Rút gọn URL đích qua Link4m
    short_url = shorten_url(target_url)
    if not short_url:
        return jsonify({"error": "Không thể tạo link rút gọn, vui lòng thử lại"}), 400

    # Nếu là 24H, tạo thêm một link trung gian
    if duration_type == "24h":
        # Tạo link2 (short) trỏ đến trang generate
        link2 = shorten_url(target_url)
        if not link2:
            return jsonify({"error": "Không thể tạo link thứ hai"}), 400
        # Nhúng link2 trực tiếp vào URL redirect (không lưu RAM) để không bị mất
        # khi server Render free tier "ngủ" (spin down) giữa lúc người dùng vượt link.
        redirect_route = f"{host}/redirect/{key}?to={quote(link2, safe='')}"
        link1 = shorten_url(redirect_route)
        if not link1:
            return jsonify({"error": "Không thể tạo link trung gian"}), 400
        # Trả về link1 cho front-end
        return jsonify({"short_url": link1})
    else:
        # 12H: trả về short_url trực tiếp
        return jsonify({"short_url": short_url})

# ---- API Admin (giữ nguyên, nay đã yêu cầu đăng nhập) ----
@app.route("/api/admin/keys", methods=["GET"])
@login_required
def admin_get_keys():
    return jsonify(load_keys())

@app.route("/api/admin/create", methods=["POST"])
@login_required
def admin_create_key():
    data = request.get_json()
    duration_type = data.get("duration", "12h")
    if duration_type not in ["12h","24h","1d","3d","7d","forever"]:
        duration_type = "12h"
    key_obj, err = create_new_key(duration_type)
    if err:
        return jsonify({"error": err}), 400
    return jsonify(key_obj)

@app.route("/api/admin/delete/<int:key_id>", methods=["DELETE"])
@login_required
def admin_delete_key(key_id):
    keys = load_keys()
    new_keys = [k for k in keys if k["id"] != key_id]
    if len(new_keys) == len(keys):
        return jsonify({"error": "Không tìm thấy key"}), 404
    save_keys(new_keys)
    return jsonify({"success": True})

@app.route("/api/admin/today-count", methods=["GET"])
def admin_today_count():
    keys = load_keys()
    return jsonify({"count": count_created_today(keys), "limit": DAILY_LIMIT})

NAV_STYLE = '''
    .navbar{ position:fixed; top:0; left:0; z-index:50; padding:16px; }
    .hamburger-btn{ width:44px; height:44px; border-radius:12px; background:rgba(17,24,39,0.9); border:1px solid var(--card-border); display:flex; align-items:center; justify-content:center; cursor:pointer; backdrop-filter:blur(8px); }
    .hamburger-btn svg{ width:20px; height:20px; }
    .nav-menu{ position:fixed; top:64px; left:16px; z-index:60; width:220px; background:rgba(17,24,39,0.97); border:1px solid var(--card-border); border-radius:16px; padding:8px; backdrop-filter:blur(10px); box-shadow:0 25px 60px -20px rgba(139,92,246,0.5); display:none; flex-direction:column; gap:2px; }
    .nav-menu.show{ display:flex; }
    .nav-item{ display:flex; align-items:center; gap:10px; padding:12px 14px; border-radius:10px; text-decoration:none; color:#e5e7eb; font-size:14.5px; font-weight:600; text-align:left; background:none; border:none; cursor:pointer; width:100%; }
    .nav-item:hover, .nav-item.active-nav{ background:linear-gradient(90deg,rgba(139,92,246,0.25),rgba(236,72,153,0.18)); }
'''
NAV_HTML = '''
    <div class="navbar">
      <button class="hamburger-btn" id="hamburgerBtn" aria-label="Menu">
        <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M3 6h18M3 12h18M3 18h18" stroke="#fff" stroke-width="2" stroke-linecap="round"/></svg>
      </button>
      <div class="nav-menu" id="navMenu">
        <a class="nav-item" href="/"><span>&#127968;</span> Trang Chủ</a>
        <a class="nav-item" href="/tim-nhac"><span>&#127925;</span> Tìm Nhạc</a>
        <a class="nav-item" href="/"><span>&#128273;</span> Lấy Key</a>
        <a class="nav-item" href="/tra-cuu-key"><span>&#128269;</span> Tra Cứu Key</a>
        <a class="nav-item" href="/admin/login"><span>&#128100;</span> Admin Login</a>
      </div>
    </div>
    <script>
      (function(){ var btn=document.getElementById('hamburgerBtn'); var menu=document.getElementById('navMenu'); if(!btn||!menu) return; btn.addEventListener('click', function(e){ e.stopPropagation(); menu.classList.toggle('show'); }); document.addEventListener('click', function(e){ if(!menu.contains(e.target) && e.target!==btn){ menu.classList.remove('show'); } }); })();
    </script>
'''
BASE_CARD_STYLE = '''
    :root{ --bg-1:#150a24; --bg-2:#1c0f33; --violet:#8b5cf6; --pink:#ec4899; --card-border:rgba(139,92,246,0.35); --text-dim:#9ca3af; }
    *{ box-sizing:border-box; }
    body{ margin:0; font-family:-apple-system,'Segoe UI',Roboto,Arial,sans-serif; background:linear-gradient(160deg,var(--bg-1),var(--bg-2)); min-height:100vh; }
    .container{ max-width:480px; margin:0 auto; padding:64px 22px; text-align:center; }
    .card{ background:rgba(17,24,39,0.85); border:1px solid var(--card-border); border-radius:22px; padding:36px 24px; backdrop-filter:blur(8px); box-shadow:0 25px 60px -25px rgba(139,92,246,0.4); }
    h1{ font-size:24px; font-weight:800; margin:0 0 12px; background:linear-gradient(90deg,#8b5cf6,#ec4899); -webkit-background-clip:text; background-clip:text; color:transparent; }
    .subtitle{ color:var(--text-dim); font-size:14px; margin-bottom:24px; }
    .field{ background:rgba(8,12,22,0.75); border:1.5px solid rgba(139,92,246,0.35); border-radius:14px; padding:14px 16px; font-size:15px; color:#fff; width:100%; margin-bottom:16px; }
    .field::placeholder{ color:#6b7280; }
    .btn-primary{ width:100%; border:none; border-radius:14px; padding:16px; font-size:15px; font-weight:800; color:#fff; cursor:pointer; background:linear-gradient(90deg,#8b5cf6,#ec4899); box-shadow:0 12px 28px -10px rgba(236,72,153,0.55); }
    .msg{ margin-top:14px; font-size:13.5px; }
    .msg-err{ color:#f87171; }
    .msg-ok{ color:#34d399; }
    .table-wrap{ overflow-x:auto; margin-top:18px; }
    table{ width:100%; border-collapse:collapse; font-size:13px; color:#e5e7eb; }
    th,td{ padding:10px 8px; text-align:left; border-bottom:1px solid rgba(139,92,246,0.2); }
    th{ color:var(--text-dim); font-weight:700; }
    .del-btn{ background:rgba(248,113,113,0.15); color:#f87171; border:1px solid rgba(248,113,113,0.4); border-radius:8px; padding:6px 10px; font-size:12px; cursor:pointer; }
    .admin-menu{ display:flex; flex-wrap:wrap; gap:10px; margin-top:20px; }
    .admin-menu .item{ flex:1 1 45%; background:rgba(8,12,22,0.7); border:1.5px solid rgba(139,92,246,0.3); border-radius:14px; padding:14px 10px; font-size:12.5px; color:#e5e7eb; font-weight:700; }
    .soon{ opacity:0.55; }
'''

@app.route("/tim-nhac")
def tim_nhac():
    return f'''<!DOCTYPE html><html lang="vi"><head><meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Zeadx Ping — Tìm Nhạc</title>
    <style>{BASE_CARD_STYLE}{NAV_STYLE}</style></head><body>
    {NAV_HTML}
    <div class="container"><div class="card">
      <h1>Tìm Nhạc</h1>
      <div class="subtitle">Tính năng này đang được phát triển, sẽ sớm ra mắt.</div>
    </div></div></body></html>'''

@app.route("/tra-cuu-key")
def tra_cuu_key():
    return f'''<!DOCTYPE html><html lang="vi"><head><meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Zeadx Ping — Tra Cứu Key</title>
    <style>{BASE_CARD_STYLE}{NAV_STYLE}</style></head><body>
    {NAV_HTML}
    <div class="container"><div class="card">
      <h1>Tra Cứu Key</h1>
      <div class="subtitle">Nhập mã key để kiểm tra tình trạng</div>
      <input class="field" id="keyInput" placeholder="Nhập key, vd: ZEADX-XXXX-XXXX-XXXX" autocapitalize="characters">
      <button class="btn-primary" onclick="lookupKey()">Kiểm tra</button>
      <div id="result" class="msg"></div>
    </div></div>
    <script>
      async function lookupKey(){{
        var k = document.getElementById('keyInput').value.trim().toUpperCase();
        var result = document.getElementById('result');
        if(!k){{ result.className='msg msg-err'; result.textContent='Vui lòng nhập key'; return; }}
        result.className='msg'; result.textContent='Đang kiểm tra...';
        try{{
          var res = await fetch('/api/lookup-key?key=' + encodeURIComponent(k));
          var data = await res.json();
          if(data.found){{
            result.className='msg msg-ok';
            result.textContent = 'Key hợp lệ — Loại: ' + data.duration + (data.expired ? ' (ĐÃ HẾT HẠN)' : ' (còn hiệu lực)');
          }} else {{
            result.className='msg msg-err'; result.textContent='Không tìm thấy key này.';
          }}
        }}catch(e){{ result.className='msg msg-err'; result.textContent='Lỗi kết nối.'; }}
      }}
    </script>
    </body></html>'''

@app.route("/api/lookup-key")
def api_lookup_key():
    k = request.args.get("key", "").strip().upper()
    keys = load_keys()
    for item in keys:
        if item.get("code", "").upper() == k:
            duration = item.get("duration")
            created_at = item.get("created_at", 0)
            duration_map = {"12h": 12*60*60*1000, "24h": 24*60*60*1000, "1d": 24*60*60*1000,
                             "3d": 3*24*60*60*1000, "7d": 7*24*60*60*1000, "forever": None}
            ms = duration_map.get(duration)
            expired = False
            if ms is not None:
                expired = (time.time()*1000 - created_at) > ms
            return jsonify({"found": True, "duration": duration, "expired": expired})
    return jsonify({"found": False})

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    error = ""
    if request.method == "POST":
        u = request.form.get("username", "")
        p = request.form.get("password", "")
        if u == ADMIN_USERNAME and p == ADMIN_PASSWORD:
            session["is_admin"] = True
            return redirect("/admin")
        error = "Sai tài khoản hoặc mật khẩu"
    return f'''<!DOCTYPE html><html lang="vi"><head><meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Zeadx Ping — Admin Login</title>
    <style>{BASE_CARD_STYLE}{NAV_STYLE}</style></head><body>
    {NAV_HTML}
    <div class="container"><div class="card">
      <h1>Admin Login</h1>
      <div class="subtitle">Đăng nhập để quản lý hệ thống</div>
      <form method="POST">
        <input class="field" name="username" placeholder="Tài khoản" required>
        <input class="field" name="password" type="password" placeholder="Mật khẩu" required>
        <button class="btn-primary" type="submit">Đăng nhập</button>
      </form>
      {'<div class="msg msg-err">' + error + '</div>' if error else ''}
    </div></div></body></html>'''

@app.route("/admin/logout", methods=["POST"])
def admin_logout():
    session.pop("is_admin", None)
    return redirect("/admin/login")

@app.route("/admin")
def admin_dashboard():
    if not session.get("is_admin"):
        return redirect("/admin/login")
    return f'''<!DOCTYPE html><html lang="vi"><head><meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Zeadx Ping — Admin Panel</title>
    <style>{BASE_CARD_STYLE}{NAV_STYLE}</style></head><body>
    {NAV_HTML}
    <div class="container"><div class="card">
      <h1>Admin Panel</h1>
      <div class="subtitle">Xin chào, {ADMIN_USERNAME}</div>
      <div id="stats" class="msg"></div>
      <div class="table-wrap">
        <table id="keysTable">
          <thead><tr><th>Key</th><th>Loại</th><th></th></tr></thead>
          <tbody id="keysBody"></tbody>
        </table>
      </div>
      <div class="admin-menu">
        <div class="item soon">Key Free (sắp ra mắt)</div>
        <div class="item soon">GetKey Config (sắp ra mắt)</div>
        <div class="item soon">Web Log (sắp ra mắt)</div>
        <div class="item soon">Bảo Mật (sắp ra mắt)</div>
        <div class="item soon">Duyệt Thiết Bị (sắp ra mắt)</div>
        <div class="item soon">Check IP (sắp ra mắt)</div>
      </div>
      <form method="POST" action="/admin/logout" style="margin-top:20px;">
        <button class="btn-primary" type="submit" style="background:linear-gradient(90deg,#f87171,#ec4899);">Đăng Xuất</button>
      </form>
    </div></div>
    <script>
      async function loadStats(){{
        var res = await fetch('/api/admin/today-count'); var d = await res.json();
        document.getElementById('stats').innerHTML = 'Đã tạo hôm nay: <b>' + d.count + ' / ' + d.limit + '</b>';
      }}
      async function loadKeys(){{
        var res = await fetch('/api/admin/keys');
        if(res.status===401){{ window.location.href='/admin/login'; return; }}
        var keys = await res.json();
        var body = document.getElementById('keysBody'); body.innerHTML='';
        keys.slice().reverse().forEach(function(k){{
          var tr = document.createElement('tr');
          tr.innerHTML = '<td>'+k.code+'</td><td>'+k.duration+'</td><td><button class="del-btn" onclick="delKey('+k.id+')">Xóa</button></td>';
          body.appendChild(tr);
        }});
      }}
      async function delKey(id){{
        if(!confirm('Xóa key này?')) return;
        await fetch('/api/admin/delete/'+id, {{method:'DELETE'}});
        loadKeys();
      }}
      loadStats(); loadKeys();
    </script>
    </body></html>'''

# ---- Chạy server ----
if __name__ == "__main__":
    if not os.path.exists(KEY_FILE):
        save_keys([])
    port = int(os.environ.get("PORT", 5005))
    debug_mode = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(host="0.0.0.0", port=port, debug=debug_mode)