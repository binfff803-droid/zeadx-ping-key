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
from datetime import timedelta
app.permanent_session_lifetime = timedelta(days=30)
CORS(app)

from werkzeug.security import generate_password_hash, check_password_hash

# QUAN TRỌNG: repo GitHub của bạn đang để Public, ai cũng xem được thông tin dưới đây.
# Mật khẩu KHÔNG còn lưu dạng chữ thường — đây là bản mã hoá (hash), không thể đọc ngược lại
# thành mật khẩu gốc dù ai đó xem được source code. Nên đổi mật khẩu định kỳ.
ADMIN_USERNAME = "Zeadxvnstore"
ADMIN_PASSWORD_HASH = "scrypt:32768:8:1$J9cHJFiQVEs1zTPv$1edc32a8dc888a192d63d1a8bb72eb319c2982bc91fdeb3ffdbe62f356f0396d32c20adf78e5621a3bfdea89cb24e7261aa60870425c20666747f6eb6f454f11"

KEY_FILE = "keys.json"

def login_required(f):
    from functools import wraps
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("is_admin"):
            return jsonify({"error": "Chưa đăng nhập"}), 401
        return f(*args, **kwargs)
    return wrapper

def page_login_required(f):
    from functools import wraps
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("is_admin"):
            return redirect("/admin/login")
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

def create_new_key(duration_type, note="", max_devices=1, key_type="premium"):
    keys = load_keys()
    if count_created_today(keys) >= DAILY_LIMIT:
        return None, f"Đã đạt giới hạn {DAILY_LIMIT} key/ngày"
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
        "used": False,
        "note": note,
        "max_devices": max_devices,
        "key_type": key_type
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
    admin_link_html = '''<a href="/admin">
      <svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="9" rx="1"/><rect x="14" y="3" width="7" height="5" rx="1"/><rect x="14" y="12" width="7" height="9" rx="1"/><rect x="3" y="16" width="7" height="5" rx="1"/></svg>
      Admin Panel
    </a>''' if session.get("is_admin") else '''<a href="/admin/login">
      <svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="12" cy="8" r="4"></circle>
        <path d="M4 20c0-4.4 3.6-8 8-8s8 3.6 8 8"></path>
      </svg>
      Admin Login
    </a>'''
    html = '''<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Zeadx Ping — Trang Lấy Key</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Rajdhani:wght@500;600;700&family=Inter:wght@400;500;600;700&family=Orbitron:wght@700;800;900&display=swap" rel="stylesheet">
<style>
  :root{
    --bg-0:#020509;
    --bg-1:#040c18;
    --bg-2:#071628;
    --navy:#0a1f38;
    --ocean:#0ea5e9;
    --ocean-2:#38bdf8;
    --ocean-deep:#0369a1;
    --ice:#e6f6ff;
    --white:#f7fbff;
    --line:rgba(56,189,248,0.18);
    --glass:rgba(10,25,45,0.55);
  }
  *{margin:0;padding:0;box-sizing:border-box;}
  html,body{height:100%;}
  body{
    font-family:'Inter',sans-serif;
    background:
      radial-gradient(ellipse 900px 500px at 50% -10%, rgba(14,165,233,0.20), transparent 60%),
      radial-gradient(ellipse 700px 600px at 90% 100%, rgba(3,105,161,0.25), transparent 55%),
      linear-gradient(180deg, var(--bg-0) 0%, var(--bg-1) 45%, var(--bg-2) 100%);
    color:var(--ice);
    min-height:100vh;
    display:flex;
    align-items:center;
    justify-content:center;
    overflow-x:hidden;
    position:relative;
    padding:40px 20px;
  }

  .sonar-field{
    position:fixed;inset:0;display:flex;align-items:center;justify-content:center;
    pointer-events:none;z-index:0;opacity:0.9;
  }
  .sonar-ring{
    position:absolute;border:1px solid rgba(56,189,248,0.35);border-radius:50%;
    animation:ping-out 4s cubic-bezier(0.2,0.6,0.4,1) infinite;
  }
  .sonar-ring:nth-child(1){width:120px;height:120px;animation-delay:0s;}
  .sonar-ring:nth-child(2){width:120px;height:120px;animation-delay:1.3s;}
  .sonar-ring:nth-child(3){width:120px;height:120px;animation-delay:2.6s;}
  @keyframes ping-out{
    0%{width:60px;height:60px;opacity:0.9;border-color:rgba(125,211,252,0.7);}
    100%{width:1400px;height:1400px;opacity:0;border-color:rgba(56,189,248,0);}
  }

  .grid-overlay{
    position:fixed;inset:0;
    background-image:linear-gradient(var(--line) 1px, transparent 1px), linear-gradient(90deg, var(--line) 1px, transparent 1px);
    background-size:48px 48px;
    mask-image:radial-gradient(ellipse 800px 500px at 50% 30%, black, transparent 75%);
    opacity:0.35;z-index:0;
  }

  .noise{
    position:fixed;inset:0;z-index:0;pointer-events:none;opacity:0.03;
    background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='100' height='100'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='2'/%3E%3C/filter%3E%3Crect width='100' height='100' filter='url(%23n)'/%3E%3C/svg%3E");
  }

  .wrap{position:relative;z-index:2;width:100%;max-width:460px;}

  .brand{text-align:center;margin-bottom:28px;}
  .brand-mark{
    display:inline-flex;align-items:center;gap:10px;padding:6px 16px;
    border:1px solid var(--line);border-radius:999px;background:rgba(14,165,233,0.06);
    font-family:'Rajdhani',sans-serif;font-size:12px;letter-spacing:0.28em;text-transform:uppercase;
    color:var(--ocean-2);margin-bottom:22px;
  }
  .brand-mark .dot{
    width:7px;height:7px;border-radius:50%;background:#4ade80;
    box-shadow:0 0 8px #4ade80, 0 0 16px #4ade80;animation:blink 1.8s ease-in-out infinite;
  }
  @keyframes blink{0%,100%{opacity:1;}50%{opacity:0.35;}}

  h1{
    font-family:'Orbitron',sans-serif;font-weight:900;font-size:40px;letter-spacing:0.02em;line-height:1;
    background:linear-gradient(180deg,#ffffff 10%, #bfe9ff 55%, var(--ocean-2) 100%);
    -webkit-background-clip:text;background-clip:text;color:transparent;
    text-shadow:0 0 40px rgba(56,189,248,0.25);
  }
  h1 span{
    display:block;font-family:'Rajdhani',sans-serif;font-weight:600;font-size:14px;letter-spacing:0.35em;
    text-transform:uppercase;color:rgba(230,246,255,0.55);-webkit-text-fill-color:rgba(230,246,255,0.55);margin-top:10px;
  }

  .card{
    position:relative;margin-top:32px;
    background:linear-gradient(180deg, rgba(12,30,52,0.75), rgba(4,12,24,0.85));
    backdrop-filter:blur(18px);border:1px solid var(--line);border-radius:6px;padding:34px 30px 30px;
    box-shadow:0 0 0 1px rgba(56,189,248,0.05), 0 30px 60px -20px rgba(0,0,0,0.7), 0 0 80px -30px rgba(14,165,233,0.4);
  }
  .corner{position:absolute;width:16px;height:16px;border:2px solid var(--ocean-2);opacity:0.9;}
  .corner.tl{top:-1px;left:-1px;border-right:none;border-bottom:none;border-radius:6px 0 0 0;}
  .corner.br{bottom:-1px;right:-1px;border-left:none;border-top:none;border-radius:0 0 6px 0;}

  .card-label{
    font-family:'Rajdhani',sans-serif;font-size:13px;font-weight:600;letter-spacing:0.22em;text-transform:uppercase;
    color:rgba(230,246,255,0.45);margin-bottom:16px;display:flex;align-items:center;gap:10px;
  }
  .card-label::after{content:"";flex:1;height:1px;background:linear-gradient(90deg, rgba(56,189,248,0.3), transparent);}

  .options{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:22px;}
  .opt{
    position:relative;cursor:pointer;border-radius:4px;border:1px solid rgba(56,189,248,0.2);
    background:rgba(4,12,24,0.6);padding:18px 14px 16px;text-align:left;
    transition:border-color .2s ease, background .2s ease, transform .15s ease;-webkit-tap-highlight-color:transparent;
  }
  .opt:hover{border-color:rgba(56,189,248,0.5);transform:translateY(-2px);}
  .opt input{position:absolute;opacity:0;pointer-events:none;}
  .opt-time{font-family:'Orbitron',sans-serif;font-weight:800;font-size:22px;color:var(--white);display:flex;align-items:baseline;gap:4px;}
  .opt-time small{font-family:'Rajdhani',sans-serif;font-size:12px;font-weight:600;color:rgba(230,246,255,0.5);}
  .opt-desc{margin-top:6px;font-family:'Rajdhani',sans-serif;font-size:12px;color:rgba(230,246,255,0.45);letter-spacing:0.03em;}
  .opt-radio{position:absolute;top:14px;right:14px;width:16px;height:16px;border-radius:50%;border:1.5px solid rgba(56,189,248,0.4);}
  .opt-radio::after{content:"";position:absolute;inset:3px;border-radius:50%;background:var(--ocean-2);transform:scale(0);transition:transform .15s ease;}
  .opt.active{
    border-color:var(--ocean-2);background:linear-gradient(135deg, rgba(14,165,233,0.14), rgba(4,12,24,0.6));
    box-shadow:0 0 0 1px rgba(56,189,248,0.3), 0 0 24px -6px rgba(56,189,248,0.5);
  }
  .opt.active .opt-radio::after{transform:scale(1);}
  .opt.active .opt-time{color:var(--ocean-2);}

  .get-key{
    width:100%;position:relative;overflow:hidden;border:none;border-radius:12px;padding:16px;cursor:pointer;
    font-family:'Rajdhani',sans-serif;font-weight:700;font-size:16px;letter-spacing:0.18em;text-transform:uppercase;
    color:#031018;background:linear-gradient(135deg, #7dd3fc, var(--ocean) 55%, var(--ocean-deep));
    box-shadow:0 8px 24px -8px rgba(14,165,233,0.7);transition:transform .12s ease, box-shadow .2s ease;
  }
  .get-key:hover{transform:translateY(-1px);box-shadow:0 12px 30px -8px rgba(56,189,248,0.85);}
  .get-key:active{transform:translateY(0px) scale(0.99);}
  .get-key .shine{
    position:absolute;top:0;bottom:0;left:-60%;width:40%;
    background:linear-gradient(120deg, transparent, rgba(255,255,255,0.55), transparent);
    transform:skewX(-20deg);animation:shine 3.2s ease-in-out infinite;
  }
  @keyframes shine{0%{left:-60%;}55%{left:130%;}100%{left:130%;}}
  .get-key.loading{pointer-events:none;opacity:0.85;}
  .get-key .btn-text{position:relative;z-index:2;display:flex;align-items:center;justify-content:center;gap:10px;}
  .spinner{
    width:15px;height:15px;border-radius:50%;border:2px solid rgba(3,16,24,0.25);
    border-top-color:#031018;animation:spin .7s linear infinite;display:none;
  }
  .get-key.loading .spinner{display:inline-block;}
  @keyframes spin{to{transform:rotate(360deg);}}

  .err-msg{margin-top:16px;text-align:center;font-family:'Rajdhani',sans-serif;font-size:13px;font-weight:600;color:#f87171;display:none;}
  .err-msg.show{display:block;}

  .foot{margin-top:22px;text-align:center;font-family:'Rajdhani',sans-serif;font-size:11.5px;letter-spacing:0.08em;color:rgba(230,246,255,0.35);}
  .foot b{color:rgba(230,246,255,0.55);}

  @media (max-width:420px){ h1{font-size:32px;} .card{padding:26px 20px 22px;} }

  .music-wrap{
    position:fixed;top:16px;right:16px;z-index:20;
  }
  .speaker-btn{
    width:44px;height:44px;border-radius:12px;
    background:rgba(10,25,45,0.7);border:1px solid var(--line);backdrop-filter:blur(10px);
    display:flex;align-items:center;justify-content:center;cursor:pointer;
  }
  .speaker-btn svg{ width:20px;height:20px;stroke:#38bdf8; }
  @media (max-width:420px){ .music-wrap{top:12px;right:12px;} }
</style>

</head>
<body>

  <div class="music-wrap">
    <audio id="genSound" src="/static/key-sound.mp3" loop preload="auto"></audio>
    <button class="speaker-btn" id="speakerBtn" aria-label="Bật/tắt nhạc">
      <svg id="speakerIcon" viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 5 6 9H2v6h4l5 4V5Z"/><path d="M15.5 8.5a5 5 0 0 1 0 7"/><path d="M18.5 5.5a9 9 0 0 1 0 13"/></svg>
    </button>
  </div>

  <div class="sonar-field">
    <div class="sonar-ring"></div>
    <div class="sonar-ring"></div>
    <div class="sonar-ring"></div>
  </div>
  <div class="grid-overlay"></div>
  <div class="noise"></div>

  <div class="wrap">
    <div class="brand">
      <div class="brand-mark"><span class="dot"></span> Server Online — Ổn Định</div>
      <h1>ZEADX PING<span>Trang Lấy Key</span></h1>
    </div>

    <div class="card">
      <div class="corner tl"></div>
      <div class="corner br"></div>

      <div class="card-label">Chọn thời hạn Key</div>

      <div class="options">
        <label class="opt active" id="opt12">
          <input type="radio" name="duration" value="12" checked>
          <span class="opt-radio"></span>
          <div class="opt-time">12<small>GIỜ</small></div>
          <div class="opt-desc">Key 12H — dùng nhanh</div>
        </label>

        <label class="opt" id="opt24">
          <input type="radio" name="duration" value="24">
          <span class="opt-radio"></span>
          <div class="opt-time">24<small>GIỜ</small></div>
          <div class="opt-desc">Key 24H — dùng cả ngày</div>
        </label>
      </div>

      <button class="get-key" id="getKeyBtn">
        <span class="shine"></span>
        <span class="btn-text">
          <span class="spinner"></span>
          <span id="btnLabel">GET KEY</span>
        </span>
      </button>

      <div class="err-msg" id="errMsg"></div>
    </div>

    <div class="foot">ZEADX PING © 2026 · Vui lòng không chia sẻ Key cho người khác · Hạn dùng <b id="footDuration">12 Giờ</b></div>
  </div>

<script>
  const opt12 = document.getElementById(\'opt12\');
  const opt24 = document.getElementById(\'opt24\');
  const footDuration = document.getElementById(\'footDuration\');
  const getKeyBtn = document.getElementById(\'getKeyBtn\');
  const btnLabel = document.getElementById(\'btnLabel\');
  const errMsg = document.getElementById(\'errMsg\');
  const genSound = document.getElementById(\'genSound\');

  (function(){
    var savedTime = parseFloat(localStorage.getItem(\'zeadxMusicTime\') || \'0\');
    var mutedPref = localStorage.getItem(\'zeadxMusicMuted\') === \'1\';
    if(savedTime > 0 && isFinite(savedTime)){
      genSound.addEventListener(\'loadedmetadata\', function(){
        if(savedTime < genSound.duration){ genSound.currentTime = savedTime; }
      }, {once:true});
    }
    if(!mutedPref){
      var tryPlay = function(){ genSound.play().catch(function(){}); };
      tryPlay();
      document.addEventListener(\'click\', tryPlay, {once:true});
    }
    genSound.addEventListener(\'play\', function(){ localStorage.setItem(\'zeadxMusicPlaying\', \'1\'); });
    genSound.addEventListener(\'pause\', function(){ localStorage.setItem(\'zeadxMusicPlaying\', \'0\'); });
    genSound.addEventListener(\'timeupdate\', function(){ localStorage.setItem(\'zeadxMusicTime\', genSound.currentTime); });

    var speakerBtn = document.getElementById(\'speakerBtn\');
    var speakerIcon = document.getElementById(\'speakerIcon\');
    var iconOn = \'<path d="M11 5 6 9H2v6h4l5 4V5Z"/><path d="M15.5 8.5a5 5 0 0 1 0 7"/><path d="M18.5 5.5a9 9 0 0 1 0 13"/>\';
    var iconOff = \'<path d="M11 5 6 9H2v6h4l5 4V5Z"/><path d="M23 9l-6 6M17 9l6 6"/>\';
    var muted = localStorage.getItem(\'zeadxMusicMuted\') === \'1\';
    genSound.muted = muted;
    speakerIcon.innerHTML = muted ? iconOff : iconOn;
    speakerBtn.addEventListener(\'click\', function(){
      genSound.muted = !genSound.muted;
      speakerIcon.innerHTML = genSound.muted ? iconOff : iconOn;
      localStorage.setItem(\'zeadxMusicMuted\', genSound.muted ? \'1\' : \'0\');
      if(!genSound.muted){ genSound.play().catch(function(){}); }
    });
  })();

  let selected = \'12\';

  function selectOpt(which){
    selected = which;
    if(which === \'12\'){
      opt12.classList.add(\'active\'); opt24.classList.remove(\'active\');
      footDuration.textContent = \'12 Giờ\';
    } else {
      opt24.classList.add(\'active\'); opt12.classList.remove(\'active\');
      footDuration.textContent = \'24 Giờ\';
    }
    errMsg.classList.remove(\'show\');
  }
  opt12.addEventListener(\'click\', () => selectOpt(\'12\'));
  opt24.addEventListener(\'click\', () => selectOpt(\'24\'));

  function setLoading(isLoading){
    getKeyBtn.classList.toggle(\'loading\', isLoading);
    btnLabel.textContent = isLoading ? \'ĐANG TẠO KEY...\' : \'GET KEY\';
  }

  getKeyBtn.addEventListener(\'click\', function(){
    try{ genSound.currentTime = 0; genSound.play(); }catch(e){}
    errMsg.classList.remove(\'show\');
    setLoading(true);
    const hours = selected === \'24\' ? \'24\' : \'12\';
    fetch(\'/api/generate\', {
      method: \'POST\',
      headers: {\'Content-Type\': \'application/json\'},
      body: JSON.stringify({hours: hours})
    }).then(res => res.json()).then(data => {
      if(data.error){
        setLoading(false);
        errMsg.textContent = data.error;
        errMsg.classList.add(\'show\');
        return;
      }
      if(data.short_url){
        window.location.href = data.short_url;
      } else {
        setLoading(false);
        errMsg.textContent = \'Không thể tạo link, vui lòng thử lại\';
        errMsg.classList.add(\'show\');
      }
    }).catch(err => {
      setLoading(false);
      errMsg.textContent = \'Lỗi kết nối đến server: \' + err;
      errMsg.classList.add(\'show\');
    });
  });
</script>

</body>
</html>'''
    return html.replace('__ADMIN_NAV_LINK__', admin_link_html)

@app.route("/generate")
def show_key():
    key = request.args.get('key', 'ZEADX-XXXX-XXXX-XXXX')
    duration = request.args.get('duration', '12H')
    return f'''<!DOCTYPE html>
    <html lang="vi">
    <head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Zeadx Ping — Đã Tạo Key</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Rajdhani:wght@500;600;700&family=Inter:wght@400;500;600;700&family=Orbitron:wght@700;800;900&display=swap" rel="stylesheet">
    <style>
      :root{{ --bg-0:#020509; --bg-1:#040c18; --bg-2:#071628; --ocean:#0ea5e9; --ocean-2:#38bdf8; --ocean-deep:#0369a1; --ice:#e6f6ff; --white:#f7fbff; --line:rgba(56,189,248,0.18); --green:#4ade80; }}
      *{{ box-sizing:border-box; }}
      html,body{{ height:100%; margin:0; }}
      body{{
        font-family:'Inter',sans-serif;
        background:
          radial-gradient(ellipse 900px 500px at 50% -10%, rgba(14,165,233,0.20), transparent 60%),
          radial-gradient(ellipse 700px 600px at 90% 100%, rgba(3,105,161,0.25), transparent 55%),
          linear-gradient(180deg, var(--bg-0) 0%, var(--bg-1) 45%, var(--bg-2) 100%);
        color:var(--ice); min-height:100vh; display:flex; align-items:center; justify-content:center; padding:40px 20px; position:relative; overflow-x:hidden;
      }}
      .grid-overlay{{ position:fixed; inset:0; background-image:linear-gradient(var(--line) 1px, transparent 1px), linear-gradient(90deg, var(--line) 1px, transparent 1px); background-size:48px 48px; mask-image:radial-gradient(ellipse 800px 500px at 50% 30%, black, transparent 75%); opacity:0.35; z-index:0; }}
      .card{{
        position:relative; z-index:2; max-width:460px; width:100%;
        background:linear-gradient(180deg, rgba(12,30,52,0.75), rgba(4,12,24,0.85));
        backdrop-filter:blur(18px); border:1px solid var(--line); border-radius:6px; padding:38px 30px 30px; text-align:center;
        box-shadow:0 0 0 1px rgba(56,189,248,0.05), 0 30px 60px -20px rgba(0,0,0,0.7), 0 0 80px -30px rgba(14,165,233,0.4);
      }}
      .corner{{ position:absolute; width:16px; height:16px; border:2px solid var(--ocean-2); opacity:0.9; }}
      .corner.tl{{ top:-1px; left:-1px; border-right:none; border-bottom:none; border-radius:6px 0 0 0; }}
      .corner.br{{ bottom:-1px; right:-1px; border-left:none; border-top:none; border-radius:0 0 6px 0; }}
      .check-wrap{{ width:88px; height:88px; margin:0 auto 22px; border-radius:50%; background:radial-gradient(circle at 50% 40%, rgba(74,222,128,0.22) 0%, transparent 70%); display:flex; align-items:center; justify-content:center; box-shadow:0 0 0 1px rgba(74,222,128,0.35), 0 0 40px 6px rgba(74,222,128,0.3); }}
      .check-wrap svg{{ width:42px; height:42px; }}
      h1{{ font-family:'Orbitron',sans-serif; font-weight:800; font-size:23px; letter-spacing:0.01em; margin:0 0 10px;
        background:linear-gradient(180deg,#ffffff 10%, #bfe9ff 55%, var(--ocean-2) 100%);
        -webkit-background-clip:text; background-clip:text; color:transparent; text-shadow:0 0 40px rgba(56,189,248,0.25); }}
      .subtitle{{ font-family:'Rajdhani',sans-serif; font-size:14px; color:rgba(230,246,255,0.5); margin-bottom:22px; letter-spacing:0.02em; }}
      .key-box{{ background:rgba(4,12,24,0.75); border:1px solid rgba(56,189,248,0.3); border-radius:6px; padding:16px 16px; display:flex; align-items:center; justify-content:space-between; gap:10px; }}
      .key-code{{ font-family:'Rajdhani',sans-serif; font-size:16px; font-weight:700; color:var(--white); letter-spacing:1.5px; word-break:break-all; text-align:left; }}
      .copy-btn{{ display:flex; align-items:center; gap:6px; border:none; border-radius:8px; padding:10px 14px; font-family:'Rajdhani',sans-serif; font-size:12.5px; font-weight:700; letter-spacing:0.05em; text-transform:uppercase; color:#031018; cursor:pointer; background:linear-gradient(135deg, #7dd3fc, var(--ocean) 55%, var(--ocean-deep)); box-shadow:0 8px 20px -8px rgba(14,165,233,0.6); white-space:nowrap; }}
      .copy-btn svg{{ width:14px; height:14px; stroke:#031018; }}
      .copy-btn.copied{{ background:linear-gradient(135deg, #86efac, var(--green) 60%, #16a34a); }}
      .key-info-row{{ display:flex; justify-content:space-between; margin-top:16px; font-family:'Rajdhani',sans-serif; font-size:12.5px; color:rgba(230,246,255,0.5); letter-spacing:0.03em; text-transform:uppercase; }}
      .key-info-row .val{{ color:var(--ocean-2); font-weight:700; }}
      .btn-primary{{
        width:100%; border:none; border-radius:12px; padding:16px; cursor:pointer; margin-top:24px;
        font-family:'Rajdhani',sans-serif; font-weight:700; font-size:15px; letter-spacing:0.14em; text-transform:uppercase;
        color:#031018; background:linear-gradient(135deg, #7dd3fc, var(--ocean) 55%, var(--ocean-deep));
        box-shadow:0 8px 24px -8px rgba(14,165,233,0.7); transition:transform .12s ease, box-shadow .2s ease;
      }}
      .btn-primary:hover{{ transform:translateY(-1px); box-shadow:0 12px 30px -8px rgba(56,189,248,0.85); }}
      .back-link{{ margin-top:16px; font-family:'Rajdhani',sans-serif; font-size:12.5px; letter-spacing:0.05em; color:rgba(230,246,255,0.45); cursor:pointer; }}
      .back-link:hover{{ color:var(--ocean-2); }}
      .footer-note{{ margin-top:26px; font-family:'Rajdhani',sans-serif; font-size:12.5px; color:rgba(230,246,255,0.4); letter-spacing:0.03em; }}
      .zalo-numbers{{ color:var(--ocean-2); font-weight:700; }}
      .copyright{{ margin-top:20px; font-family:'Rajdhani',sans-serif; font-size:11px; letter-spacing:0.05em; color:rgba(230,246,255,0.25); }}
    </style>
    </head>
    <body>
    <div class="grid-overlay"></div>
    <div class="card">
      <div class="corner tl"></div>
      <div class="corner br"></div>
      <div class="check-wrap">
        <svg viewBox="0 0 24 24" fill="none" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6L9 17l-5-5" stroke="#4ade80"/></svg>
      </div>
      <h1>Hệ Thống Đã Tạo Xong Key</h1>
      <div class="subtitle">Key của bạn đã sẵn sàng, hãy sao chép và sử dụng ngay</div>
      <div class="key-box">
        <div class="key-code" id="keyCode">{key}</div>
        <button class="copy-btn" id="copyBtn">
          <svg id="copyIcon" viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="12" height="12" rx="2"/><path d="M5 15V5a2 2 0 0 1 2-2h10"/></svg>
          <span id="copyLabel">Copy</span>
        </button>
      </div>
      <div class="key-info-row">
        <span>Thời hạn: <span class="val">{duration}</span></span>
        <span>Trạng thái: <span class="val" style="color:#4ade80">Chưa dùng</span></span>
      </div>
      <button class="btn-primary" onclick="location.href='/'">TẠO KEY MỚI</button>
      <div class="back-link" onclick="location.href='/'">&#8592; Quay lại trang lấy Key</div>
      <div class="footer-note">Mua Key — Inbox Zalo: <span class="zalo-numbers">0961291657</span> hoặc <span class="zalo-numbers">0938738602</span></div>
      <div class="copyright">© 2026 ZEADX PING KEY | All Rights Reserved.</div>
    </div>
    <script>
      var checkIconSVG = '<path d="M20 6L9 17l-5-5"/>';
      var copySVG = '<rect x="9" y="9" width="12" height="12" rx="2"/><path d="M5 15V5a2 2 0 0 1 2-2h10"/>';
      document.getElementById('copyBtn').addEventListener('click', function() {{
        var code = document.getElementById('keyCode').textContent;
        var btn = this;
        var icon = document.getElementById('copyIcon');
        var label = document.getElementById('copyLabel');
        function markCopied(){{
          icon.innerHTML = checkIconSVG;
          icon.setAttribute('stroke', '#031018');
          label.textContent = 'Đã Copy';
          btn.classList.add('copied');
          setTimeout(function(){{ icon.innerHTML = copySVG; label.textContent = 'Copy'; btn.classList.remove('copied'); }}, 1500);
        }}
        if (navigator.clipboard && navigator.clipboard.writeText) {{
          navigator.clipboard.writeText(code).then(markCopied).catch(function(){{ fallbackCopy(code); markCopied(); }});
        }} else {{
          fallbackCopy(code); markCopied();
        }}
      }});
      function fallbackCopy(text) {{
        var ta = document.createElement('textarea');
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
    note = str(data.get("note", ""))[:200]
    try:
        max_devices = max(1, min(50, int(data.get("max_devices", 1))))
    except (TypeError, ValueError):
        max_devices = 1
    try:
        quantity = max(1, min(20, int(data.get("quantity", 1))))
    except (TypeError, ValueError):
        quantity = 1
    key_type = data.get("key_type", "premium")
    if key_type not in ["premium", "vip"]:
        key_type = "premium"

    created = []
    for _ in range(quantity):
        key_obj, err = create_new_key(duration_type, note=note, max_devices=max_devices, key_type=key_type)
        if err:
            if created:
                return jsonify({"keys": created, "error": err})
            return jsonify({"error": err}), 400
        created.append(key_obj)
    return jsonify({"keys": created})

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
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Rajdhani:wght@500;600;700&family=Inter:wght@400;500;600;700&family=Orbitron:wght@700;800;900&display=swap" rel="stylesheet">
    <style>
      :root{ --bg-0:#020509; --bg-1:#040c18; --bg-2:#071628; --ocean:#0ea5e9; --ocean-2:#38bdf8; --ocean-deep:#0369a1; --ice:#e6f6ff; --white:#f7fbff; --line:rgba(56,189,248,0.18); }
      *{ box-sizing:border-box; }
      html,body{ height:100%; margin:0; }
      body{
        font-family:'Inter',sans-serif;
        background:
          radial-gradient(ellipse 900px 500px at 50% -10%, rgba(14,165,233,0.20), transparent 60%),
          radial-gradient(ellipse 700px 600px at 90% 100%, rgba(3,105,161,0.25), transparent 55%),
          linear-gradient(180deg, var(--bg-0) 0%, var(--bg-1) 45%, var(--bg-2) 100%);
        color:var(--ice); min-height:100vh; position:relative; overflow-x:hidden;
      }
      .grid-overlay{ position:fixed; inset:0; background-image:linear-gradient(var(--line) 1px, transparent 1px), linear-gradient(90deg, var(--line) 1px, transparent 1px); background-size:48px 48px; mask-image:radial-gradient(ellipse 800px 500px at 50% 30%, black, transparent 75%); opacity:0.35; z-index:0; }
      .container{ position:relative; z-index:2; max-width:460px; margin:0 auto; padding:90px 20px 40px; text-align:center; }
      .card{
        position:relative; background:linear-gradient(180deg, rgba(12,30,52,0.75), rgba(4,12,24,0.85));
        backdrop-filter:blur(18px); border:1px solid var(--line); border-radius:6px; padding:34px 30px 30px;
        box-shadow:0 0 0 1px rgba(56,189,248,0.05), 0 30px 60px -20px rgba(0,0,0,0.7), 0 0 80px -30px rgba(14,165,233,0.4);
        animation:slideUpIn .5s cubic-bezier(0.2,0.7,0.3,1) both;
      }
      @keyframes slideUpIn{ from{ opacity:0; transform:translateY(28px); } to{ opacity:1; transform:translateY(0); } }
      .music-wrap{ position:fixed; top:16px; right:16px; z-index:20; width:230px; max-width:44vw; }
      .music-bar{ width:100%; height:38px; border-radius:10px; background:rgba(10,25,45,0.7); border:1px solid var(--line); backdrop-filter:blur(10px); accent-color:#38bdf8; }
      .music-bar::-webkit-media-controls-panel{ background-color:rgba(10,25,45,0.9); }
      .music-bar::-webkit-media-controls-play-button,
      .music-bar::-webkit-media-controls-mute-button{ filter:invert(80%) sepia(40%) saturate(900%) hue-rotate(160deg); }
      .music-bar::-webkit-media-controls-current-time-display,
      .music-bar::-webkit-media-controls-time-remaining-display{ color:#f7fbff; }
      @media (max-width:420px){ .music-wrap{ width:170px; top:12px; right:12px; } }
      h1{ font-family:'Orbitron',sans-serif; font-weight:800; font-size:26px; letter-spacing:0.02em;
        background:linear-gradient(180deg,#ffffff 10%, #bfe9ff 55%, var(--ocean-2) 100%);
        -webkit-background-clip:text; background-clip:text; color:transparent; margin:0 0 12px;
        text-shadow:0 0 40px rgba(56,189,248,0.25); }
      .subtitle{ font-family:'Rajdhani',sans-serif; font-size:14px; color:rgba(230,246,255,0.5); margin-bottom:22px; letter-spacing:0.02em; }
      .field{
        width:100%; background:rgba(4,12,24,0.7); border:1px solid rgba(56,189,248,0.25); border-radius:6px;
        padding:14px 15px; color:var(--white); font-family:'Inter',sans-serif; font-size:14.5px; margin-bottom:14px; outline:none;
        transition:border-color .2s ease, box-shadow .2s ease;
      }
      .field::placeholder{ color:rgba(230,246,255,0.35); }
      .field:focus{ border-color:var(--ocean-2); box-shadow:0 0 0 3px rgba(56,189,248,0.15); }
      .btn-primary{
        width:100%; border:none; border-radius:12px; padding:16px; cursor:pointer;
        font-family:'Rajdhani',sans-serif; font-weight:700; font-size:15px; letter-spacing:0.14em; text-transform:uppercase;
        color:#031018; background:linear-gradient(135deg, #7dd3fc, var(--ocean) 55%, var(--ocean-deep));
        box-shadow:0 8px 24px -8px rgba(14,165,233,0.7); transition:transform .12s ease, box-shadow .2s ease;
      }
      .btn-primary:hover{ transform:translateY(-1px); box-shadow:0 12px 30px -8px rgba(56,189,248,0.85); }
      .msg{ margin-top:14px; font-family:'Rajdhani',sans-serif; font-size:13.5px; font-weight:600; }
      .msg-err{ color:#f87171; }
      .msg-ok{ color:#4ade80; }
      .table-wrap{ overflow-x:auto; margin-top:18px; }
      table{ width:100%; border-collapse:collapse; font-size:13px; color:var(--ice); font-family:'Inter',sans-serif; }
      th,td{ padding:10px 8px; text-align:left; border-bottom:1px solid rgba(56,189,248,0.15); }
      th{ color:rgba(230,246,255,0.5); font-weight:700; font-family:'Rajdhani',sans-serif; letter-spacing:0.05em; text-transform:uppercase; font-size:12px; }
      .del-btn{ background:rgba(248,113,113,0.12); color:#f87171; border:1px solid rgba(248,113,113,0.4); border-radius:6px; padding:6px 10px; font-size:12px; cursor:pointer; font-family:'Rajdhani',sans-serif; font-weight:700; }
      .admin-menu{ display:flex; flex-wrap:wrap; gap:10px; margin-top:20px; }
      .admin-menu .item{ flex:1 1 45%; background:rgba(4,12,24,0.6); border:1px solid rgba(56,189,248,0.2); border-radius:6px; padding:14px 10px; font-family:'Rajdhani',sans-serif; font-size:12.5px; letter-spacing:0.03em; color:rgba(230,246,255,0.7); font-weight:700; }
      .soon{ opacity:0.5; }
    </style>
'''
def music_widget():
    return '''
    <div class="music-wrap">
      <audio id="genSound" src="/static/key-sound.mp3" loop preload="auto"></audio>
      <button class="speaker-btn" id="speakerBtn" aria-label="Bat/tat nhac">
        <svg id="speakerIcon" viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 5 6 9H2v6h4l5 4V5Z"/><path d="M15.5 8.5a5 5 0 0 1 0 7"/><path d="M18.5 5.5a9 9 0 0 1 0 13"/></svg>
      </button>
    </div>
    <style>
      .music-wrap{ position:fixed; top:16px; right:16px; z-index:20; }
      .speaker-btn{ width:44px; height:44px; border-radius:12px; background:rgba(10,25,45,0.7); border:1px solid var(--line); backdrop-filter:blur(10px); display:flex; align-items:center; justify-content:center; cursor:pointer; }
      .speaker-btn svg{ width:20px; height:20px; stroke:#38bdf8; }
      @media (max-width:420px){ .music-wrap{ top:12px; right:12px; } }
    </style>
    <script>
      (function(){
        var audio = document.getElementById(\'genSound\');
        if(!audio) return;
        var mutedPref = localStorage.getItem(\'zeadxMusicMuted\') === \'1\';
        var savedTime = parseFloat(localStorage.getItem(\'zeadxMusicTime\') || \'0\');
        if(savedTime > 0 && isFinite(savedTime)){
          audio.addEventListener(\'loadedmetadata\', function(){
            if(savedTime < audio.duration){ audio.currentTime = savedTime; }
          }, {once:true});
        }
        if(!mutedPref){
          var tryPlay = function(){ audio.play().catch(function(){}); };
          tryPlay();
          document.addEventListener(\'click\', tryPlay, {once:true});
        }
        audio.addEventListener(\'play\', function(){ localStorage.setItem(\'zeadxMusicPlaying\', \'1\'); });
        audio.addEventListener(\'pause\', function(){ localStorage.setItem(\'zeadxMusicPlaying\', \'0\'); });
        audio.addEventListener(\'timeupdate\', function(){ localStorage.setItem(\'zeadxMusicTime\', audio.currentTime); });

        var speakerBtn = document.getElementById(\'speakerBtn\');
        var speakerIcon = document.getElementById(\'speakerIcon\');
        var iconOn = \'<path d="M11 5 6 9H2v6h4l5 4V5Z"/><path d="M15.5 8.5a5 5 0 0 1 0 7"/><path d="M18.5 5.5a9 9 0 0 1 0 13"/>\';
        var iconOff = \'<path d="M11 5 6 9H2v6h4l5 4V5Z"/><path d="M23 9l-6 6M17 9l6 6"/>\';
        var muted = localStorage.getItem(\'zeadxMusicMuted\') === \'1\';
        audio.muted = muted;
        speakerIcon.innerHTML = muted ? iconOff : iconOn;
        speakerBtn.addEventListener(\'click\', function(){
          audio.muted = !audio.muted;
          speakerIcon.innerHTML = audio.muted ? iconOff : iconOn;
          localStorage.setItem(\'zeadxMusicMuted\', audio.muted ? \'1\' : \'0\');
          if(!audio.muted){ audio.play().catch(function(){}); }
        });
      })();
    </script>
'''
def nav_html():
    if session.get("is_admin"):
        admin_link = '''
      <a href="/admin">
        <svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="9" rx="1"/><rect x="14" y="3" width="7" height="5" rx="1"/><rect x="14" y="12" width="7" height="9" rx="1"/><rect x="3" y="16" width="7" height="5" rx="1"/></svg>
        Admin Panel
      </a>'''
    else:
        admin_link = '''
      <a href="/admin/login">
        <svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="8" r="4"/><path d="M4 20c0-4.4 3.6-8 8-8s8 3.6 8 8"/></svg>
        Admin Login
      </a>'''
    return '''
    <div class="grid-overlay"></div>
'''
BASE_CARD_STYLE = ''

@app.route("/tim-nhac")
def tim_nhac():
    return f'''<!DOCTYPE html><html lang="vi"><head><meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Zeadx Ping — Tìm Nhạc</title>
    {NAV_STYLE}</head><body>
    {nav_html()}
    <div class="container"><div class="card">
      <h1>Tìm Nhạc</h1>
      <div class="subtitle">Tính năng này đang được phát triển, sẽ sớm ra mắt.</div>
    </div></div></body></html>'''

@app.route("/tra-cuu-key")
def tra_cuu_key():
    return f'''<!DOCTYPE html><html lang="vi"><head><meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Zeadx Ping — Tra Cứu Key</title>
    {NAV_STYLE}</head><body>
    {nav_html()}
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
    if session.get("is_admin") and request.method == "GET":
        return redirect("/admin")
    error = ""
    if request.method == "POST":
        u = request.form.get("username", "")
        p = request.form.get("password", "")
        if u == ADMIN_USERNAME and check_password_hash(ADMIN_PASSWORD_HASH, p):
            session.permanent = True
            session["is_admin"] = True
            return redirect("/admin")
        error = "Sai tài khoản hoặc mật khẩu"
    return f'''<!DOCTYPE html><html lang="vi"><head><meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Zeadx Ping — Admin Login</title>
    {NAV_STYLE}
    <style>
      .input-wrap{{ position:relative; margin-bottom:14px; }}
      .input-wrap .l-ic{{ position:absolute; left:14px; top:50%; transform:translateY(-50%); width:16px; height:16px; stroke:rgba(230,246,255,0.4); pointer-events:none; }}
      .input-wrap input{{ padding-left:40px; margin-bottom:0; }}
      .input-wrap input#passwordField{{ padding-right:42px; }}
      .eye-btn{{ position:absolute; right:10px; top:50%; transform:translateY(-50%); background:none; border:none; cursor:pointer; padding:6px; display:flex; }}
      .eye-btn svg{{ width:18px; height:18px; stroke:rgba(230,246,255,0.5); }}
      .eye-btn:hover svg{{ stroke:var(--ocean-2); }}
    </style>
    </head><body>
    {nav_html()}
    <div class="container"><div class="card">
      <h1>Admin Login</h1>
      <div class="subtitle">Đăng nhập để quản lý hệ thống</div>
      <form method="POST" id="loginForm" novalidate>
        <div class="input-wrap">
          <svg class="l-ic" viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="8" r="4"/><path d="M4 20c0-4.4 3.6-8 8-8s8 3.6 8 8"/></svg>
          <input class="field" id="usernameField" name="username" placeholder="Tài khoản">
        </div>
        <div class="input-wrap">
          <svg class="l-ic" viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="5" y="11" width="14" height="9" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/></svg>
          <input class="field" id="passwordField" name="password" type="password" placeholder="Mật khẩu">
          <button type="button" class="eye-btn" id="eyeToggle" aria-label="Hiện mật khẩu">
            <svg id="eyeIcon" viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-7 11-7 11 7 11 7-4 7-11 7-11-7-11-7Z"/><circle cx="12" cy="12" r="3"/></svg>
          </button>
        </div>
        <button class="btn-primary" type="submit" style="margin-top:6px;">Đăng nhập</button>
      </form>
      <div class="msg msg-err" id="formMsg" style="{'display:block' if error else 'display:none'}">{error}</div>
    </div></div>
    <script>
      var eyeToggle = document.getElementById('eyeToggle');
      var pwField = document.getElementById('passwordField');
      var eyeIcon = document.getElementById('eyeIcon');
      var eyeOpenPath = '<path d="M1 12s4-7 11-7 11 7 11 7-4 7-11 7-11-7-11-7Z"/><circle cx="12" cy="12" r="3"/>';
      var eyeClosedPath = '<path d="M17.9 17.9A10.6 10.6 0 0 1 12 19c-7 0-11-7-11-7a19.6 19.6 0 0 1 4.2-5.2M9.9 4.2A9.7 9.7 0 0 1 12 4c7 0 11 7 11 7a19.6 19.6 0 0 1-2.6 3.6"/><path d="M1 1l22 22"/><path d="M14.1 14.1a3 3 0 1 1-4.2-4.2"/>';
      eyeToggle.addEventListener('click', function(){{
        if(pwField.type === 'password'){{ pwField.type = 'text'; eyeIcon.innerHTML = eyeClosedPath; }}
        else {{ pwField.type = 'password'; eyeIcon.innerHTML = eyeOpenPath; }}
      }});
      document.getElementById('loginForm').addEventListener('submit', function(e){{
        var u = document.getElementById('usernameField').value.trim();
        var p = document.getElementById('passwordField').value.trim();
        var msg = document.getElementById('formMsg');
        if(!u || !p){{
          e.preventDefault();
          msg.style.display = 'block';
          msg.textContent = 'Vui lòng nhập tài khoản và mật khẩu ở đây';
        }}
      }});
    </script>
    </body></html>'''

@app.route("/admin/logout", methods=["POST"])
def admin_logout():
    session.pop("is_admin", None)
    return redirect("/admin/login")

ADMIN_ROW_CSS = '''
    <style>
      .admin-list{ text-align:left; margin-top:8px; }
      .admin-row{ display:flex; align-items:center; gap:12px; padding:13px 4px; border-bottom:1px solid rgba(56,189,248,0.12); background:none; border-left:none; border-right:none; border-top:none; width:100%; cursor:pointer; text-decoration:none; color:var(--ice); font-family:'Rajdhani',sans-serif; font-weight:600; font-size:14.5px; letter-spacing:0.03em; text-transform:uppercase; }
      .admin-row:hover{ color:var(--ocean-2); }
      .admin-row svg{ width:17px; height:17px; flex-shrink:0; stroke:currentColor; }
      .admin-row.danger{ color:#f87171; }
      .admin-row.soon{ opacity:0.45; }
      select.field{ appearance:none; }
      .field-label{ font-family:'Rajdhani',sans-serif; font-size:12px; letter-spacing:0.08em; text-transform:uppercase; color:rgba(230,246,255,0.45); margin:14px 0 6px; }
      .field-label:first-of-type{ margin-top:0; }
      .key-type-row{ display:grid; grid-template-columns:1fr 1fr; gap:10px; margin-bottom:16px; }
      .key-type-opt{ display:flex; align-items:center; gap:8px; padding:12px 14px; border:1px solid rgba(56,189,248,0.25); border-radius:6px; cursor:pointer; font-family:'Rajdhani',sans-serif; font-size:13.5px; font-weight:700; color:rgba(230,246,255,0.7); }
      .key-type-opt input{ display:none; }
      .key-type-opt .radio-dot{ width:14px; height:14px; border-radius:50%; border:1.5px solid rgba(56,189,248,0.4); flex-shrink:0; position:relative; }
      .key-type-opt.active{ border-color:var(--ocean-2); background:rgba(14,165,233,0.08); color:var(--ocean-2); }
      .key-type-opt.active .radio-dot{ border-color:var(--ocean-2); }
      .key-type-opt.active .radio-dot::after{ content:""; position:absolute; inset:2.5px; border-radius:50%; background:var(--ocean-2); }
      .result-list{ margin-top:16px; }
      .result-head{ display:flex; align-items:center; gap:8px; font-family:'Rajdhani',sans-serif; font-weight:700; font-size:13.5px; color:#4ade80; margin-bottom:10px; }
      .result-head svg{ width:16px; height:16px; stroke:#4ade80; }
      .result-row{ display:flex; align-items:center; justify-content:space-between; gap:10px; background:rgba(4,12,24,0.6); border:1px solid rgba(56,189,248,0.2); border-radius:6px; padding:10px 12px; margin-bottom:8px; }
      .result-row .code{ font-family:'Rajdhani',sans-serif; font-size:13.5px; font-weight:700; color:var(--white); letter-spacing:0.5px; word-break:break-all; }
      .copy-mini{ display:flex; align-items:center; gap:5px; border:none; border-radius:6px; padding:7px 10px; font-family:'Rajdhani',sans-serif; font-size:11.5px; font-weight:700; letter-spacing:0.03em; color:#031018; cursor:pointer; background:linear-gradient(135deg, #7dd3fc, #0ea5e9 55%); white-space:nowrap; }
      .copy-mini svg{ width:12px; height:12px; stroke:#031018; }
      .copy-mini.copied{ background:linear-gradient(135deg, #86efac, #4ade80); }
      .back-link{ display:inline-flex; align-items:center; gap:6px; margin-bottom:18px; font-family:'Rajdhani',sans-serif; font-size:12.5px; letter-spacing:0.05em; color:rgba(230,246,255,0.45); text-decoration:none; }
      .back-link:hover{ color:var(--ocean-2); }
      .back-link svg{ width:14px; height:14px; }
    </style>
'''

def admin_menu_html():
    return f'''
      <div class="admin-list">
        <a class="admin-row" href="/"><svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 12l9-9 9 9"/><path d="M9 21V12h6v9"/></svg> Trang Chủ</a>
        <a class="admin-row" href="/admin/create-key"><svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M12 8v8M8 12h8"/></svg> Tạo Khóa Mới</a>
        <a class="admin-row" href="/admin/manage-keys"><svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v14c0 1.7 3.6 3 8 3s8-1.3 8-3V5"/><path d="M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3"/></svg> Quản Lý Keys</a>
        <a class="admin-row" href="/tra-cuu-key"><svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4.5 8-11V5l-8-3-8 3v6c0 6.5 8 11 8 11Z"/></svg> Kiểm Tra Key</a>
        <button class="admin-row soon" onclick="soon()"><svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 12v6a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h6"/><path d="M16 2h6v6M22 2l-9 9"/></svg> Key Free</button>
        <a class="admin-row" href="/admin/stats"><svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 20V10M12 20V4M20 20v-7"/></svg> Thống Kê Key</a>
        <button class="admin-row soon" onclick="soon()"><svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 21v-7a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v7"/><path d="M9 21v-4h6v4"/><path d="M9 3h6l1 5H8l1-5Z"/></svg> GetKey Config</button>
        <button class="admin-row soon" onclick="soon()"><svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 17l6-6-6-6"/><path d="M12 19h8"/></svg> Web Log</button>
        <button class="admin-row soon" onclick="soon()"><svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="5" y="11" width="14" height="9" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/></svg> Bảo Mật</button>
        <button class="admin-row soon" onclick="soon()"><svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="7" y="2" width="10" height="20" rx="2"/><path d="M11 18h2"/></svg> Duyệt Thiết Bị</button>
        <button class="admin-row soon" onclick="soon()"><svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18"/></svg> Check IP</button>
        <button class="admin-row soon" onclick="soon()"><svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1-1.6 1.7 1.7 0 0 0-1.9.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.9 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.6-1 1.7 1.7 0 0 0-.3-1.9l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.9.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.9-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.9V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1Z"/></svg> API Docs</button>
        <form method="POST" action="/admin/logout" style="margin:0;">
          <button class="admin-row danger" type="submit" style="border:none;background:none;"><svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><path d="M16 17l5-5-5-5"/><path d="M21 12H9"/></svg> Đăng Xuất</button>
        </form>
      </div>
    <script>function soon(){{ alert('Tính năng này đang được phát triển, sẽ sớm ra mắt.'); }}</script>
'''

BACK_LINK = '<a class="back-link" href="/admin"><svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M19 12H5M12 19l-7-7 7-7"/></svg> Quay lại Admin Panel</a>'

@app.route("/admin")
def admin_dashboard():
    if not session.get("is_admin"):
        return redirect("/admin/login")
    return f'''<!DOCTYPE html><html lang="vi"><head><meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Zeadx Ping — Admin Panel</title>
    {NAV_STYLE}
    {ADMIN_ROW_CSS}
    </head><body>
    {nav_html()}
    {music_widget()}
    <div class="container"><div class="card">
      <h1>Admin Panel</h1>
      <div class="subtitle">Xin chào, {ADMIN_USERNAME}</div>
      {admin_menu_html()}
    </div></div>
    </body></html>'''

@app.route("/admin/create-key")
@page_login_required
def admin_create_key_page():
    return f'''<!DOCTYPE html><html lang="vi"><head><meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Zeadx Ping — Tạo Khóa Mới</title>
    {NAV_STYLE}
    {ADMIN_ROW_CSS}
    </head><body>
    {nav_html()}
    {music_widget()}
    <div class="container"><div class="card">
      {BACK_LINK}
      <h1>Tạo Khóa Mới</h1>
      <div class="subtitle">Tạo key mới cho hệ thống</div>

      <div class="field-label">Thời Hạn</div>
      <select class="field" id="createDuration">
        <option value="12h">12 Giờ</option>
        <option value="24h">24 Giờ</option>
        <option value="1d">1 Ngày</option>
        <option value="3d">3 Ngày</option>
        <option value="7d">7 Ngày</option>
        <option value="forever">Vĩnh Viễn</option>
      </select>

      <div class="field-label">Hết Hạn (Dự Kiến)</div>
      <div class="field" id="expiryPreview" style="color:var(--ocean-2); font-weight:700;">—</div>

      <div class="field-label">Số Thiết Bị Tối Đa</div>
      <input class="field" id="createMaxDevices" type="number" min="1" max="50" value="1">

      <div class="field-label">Ghi Chú (Tuỳ Chọn)</div>
      <input class="field" id="createNote" placeholder="Ghi chú cho key này...">

      <div class="field-label">Số Lượng Key</div>
      <input class="field" id="createQuantity" type="number" min="1" max="20" value="1">

      <div class="field-label">Loại Key</div>
      <div class="key-type-row">
        <label class="key-type-opt active" id="typePremium">
          <input type="radio" name="keyType" value="premium" checked>
          <span class="radio-dot"></span> Premium
        </label>
        <label class="key-type-opt" id="typeVip">
          <input type="radio" name="keyType" value="vip">
          <span class="radio-dot"></span> VIP
        </label>
      </div>

      <button class="btn-primary" onclick="createKey()">
        <svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width:15px;height:15px;vertical-align:-2px;margin-right:6px;"><circle cx="7.5" cy="15.5" r="5.5"/><path d="M21 2l-9.6 9.6M15.5 7.5L18 10M12 11l3 3"/></svg>
        Tạo Key
      </button>

      <div id="createMsg" class="msg"></div>
      <div id="createResults"></div>
    </div></div>
    <script>
      function updateExpiryPreview(){{
        var duration = document.getElementById('createDuration').value;
        var msMap = {{'12h':12*3600000,'24h':24*3600000,'1d':24*3600000,'3d':3*24*3600000,'7d':7*24*3600000,'forever':null}};
        var ms = msMap[duration];
        var el = document.getElementById('expiryPreview');
        if(ms === null){{ el.textContent = 'Không hết hạn (vĩnh viễn)'; return; }}
        var d = new Date(Date.now() + ms);
        function pad(n){{ return n < 10 ? '0'+n : n; }}
        el.textContent = pad(d.getHours())+':'+pad(d.getMinutes())+':'+pad(d.getSeconds())+' '+d.getDate()+'/'+(d.getMonth()+1)+'/'+d.getFullYear();
      }}
      document.getElementById('createDuration').addEventListener('change', updateExpiryPreview);
      updateExpiryPreview();
      document.querySelectorAll('input[name="keyType"]').forEach(function(radio){{
        radio.addEventListener('change', function(){{
          document.getElementById('typePremium').classList.toggle('active', document.querySelector('input[value="premium"]').checked);
          document.getElementById('typeVip').classList.toggle('active', document.querySelector('input[value="vip"]').checked);
        }});
      }});
      async function createKey(){{
        var duration = document.getElementById('createDuration').value;
        var maxDevices = document.getElementById('createMaxDevices').value;
        var note = document.getElementById('createNote').value;
        var quantity = document.getElementById('createQuantity').value;
        var keyType = document.querySelector('input[name="keyType"]:checked').value;
        var msg = document.getElementById('createMsg');
        var results = document.getElementById('createResults');
        results.innerHTML = '';
        msg.className = 'msg'; msg.textContent = 'Đang tạo...';
        try{{
          var res = await fetch('/api/admin/create', {{
            method:'POST', headers:{{'Content-Type':'application/json'}},
            body: JSON.stringify({{duration: duration, max_devices: maxDevices, note: note, quantity: quantity, key_type: keyType}})
          }});
          var data = await res.json();
          if(data.error && !data.keys){{ msg.className='msg msg-err'; msg.textContent = data.error; return; }}
          var keys = data.keys || [];
          msg.className = 'msg msg-ok';
          msg.textContent = data.error ? ('Đã tạo được ' + keys.length + ' key trước khi: ' + data.error) : '';
          var html = '<div class="result-list"><div class="result-head">' +
            '<svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6L9 17l-5-5"/></svg>' +
            'Tạo thành công ' + keys.length + ' key</div>';
          keys.forEach(function(k, i){{
            html += '<div class="result-row"><span class="code">' + k.code + '</span>' +
              '<button class="copy-mini" onclick="copyMini(this, \\'' + k.code + '\\')">' +
              '<svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="12" height="12" rx="2"/><path d="M5 15V5a2 2 0 0 1 2-2h10"/></svg> Sao chép</button></div>';
          }});
          html += '</div>';
          results.innerHTML = html;
        }}catch(e){{ msg.className='msg msg-err'; msg.textContent = 'Lỗi kết nối.'; }}
      }}
      function copyMini(btn, code){{
        function done(){{
          var original = btn.innerHTML;
          btn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6L9 17l-5-5"/></svg> Đã chép';
          btn.classList.add('copied');
          setTimeout(function(){{ btn.innerHTML = original; btn.classList.remove('copied'); }}, 1500);
        }}
        if(navigator.clipboard && navigator.clipboard.writeText){{ navigator.clipboard.writeText(code).then(done); }}
        else {{
          var ta = document.createElement('textarea'); ta.value = code; ta.style.position='fixed'; ta.style.opacity='0';
          document.body.appendChild(ta); ta.select();
          try{{ document.execCommand('copy'); }}catch(e){{}}
          document.body.removeChild(ta); done();
        }}
      }}
    </script>
    </body></html>'''

@app.route("/admin/manage-keys")
@page_login_required
def admin_manage_keys_page():
    return f'''<!DOCTYPE html><html lang="vi"><head><meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Zeadx Ping — Quản Lý Keys</title>
    {NAV_STYLE}
    {ADMIN_ROW_CSS}
    </head><body>
    {nav_html()}
    {music_widget()}
    <div class="container"><div class="card">
      {BACK_LINK}
      <h1>Quản Lý Keys</h1>
      <div id="stats" class="msg"></div>
      <div class="table-wrap">
        <table id="keysTable">
          <thead><tr><th>Key</th><th>Loại</th><th></th></tr></thead>
          <tbody id="keysBody"></tbody>
        </table>
      </div>
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

@app.route("/admin/stats")
@page_login_required
def admin_stats_page():
    return f'''<!DOCTYPE html><html lang="vi"><head><meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Zeadx Ping — Thống Kê Key</title>
    {NAV_STYLE}
    {ADMIN_ROW_CSS}
    </head><body>
    {nav_html()}
    {music_widget()}
    <div class="container"><div class="card">
      {BACK_LINK}
      <h1>Thống Kê Key</h1>
      <div id="statsOnly" class="msg"></div>
    </div></div>
    <script>
      async function loadStatsOnly(){{
        var res = await fetch('/api/admin/today-count'); var d = await res.json();
        document.getElementById('statsOnly').innerHTML = 'Đã tạo hôm nay: <b>' + d.count + ' / ' + d.limit + '</b>';
      }}
      loadStatsOnly();
    </script>
    </body></html>'''


# ---- Chạy server ----
if __name__ == "__main__":
    if not os.path.exists(KEY_FILE):
        save_keys([])
    port = int(os.environ.get("PORT", 5005))
    debug_mode = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(host="0.0.0.0", port=port, debug=debug_mode)