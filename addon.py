"""
UID BYPASS BYPASS - addon.py
Single port (2039) — all services inline.

UID CHECK PRIORITY:
  1. spectre.dpdns.org   (your website — remote raw UID list)
  2. sigma.vexanode.cloud (backup remote raw UID list)
  3. Local whitelist.json / whitelist_*.json (offline fallback)
"""

import sys
import os
import json
import time
import threading
import requests as req_lib
from pathlib import Path

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)
sys.path.insert(0, os.path.join(BASE_DIR, "src", "protobuf"))
sys.path.insert(0, os.path.join(BASE_DIR, "access_jwt"))

from mitmproxy import http
from src.core.encryption_utils import aes_decrypt, encrypt_api
from src.protobuf.protobuf_utils import get_available_room
from src.utils.console import Console
import my_pb2
import output_pb2

# ══════════════════════════════════════════════════════════════
# REMOTE UID SERVER CONFIG
# ══════════════════════════════════════════════════════════════

# Raw UID list servers (plain text, one UID per line)
UID_SERVERS = {
    "MAIN":   "https://raw.githubusercontent.com/UIDBYPASS/uidbypass/main/uidbypass/raw/uid",
    "BACKUP": "https://raw.githubusercontent.com/UIDBYPASS/uidbypass/main/uidbypass/raw/uid",
}

UID_SYNC_INTERVAL = 60   # seconds between remote syncs
UID_TTL_SECONDS   = 24 * 60 * 60  # 1 day

# In-memory UID cache: { "MAIN": set(), "BACKUP": set() }
_uid_cache: dict[str, set] = {}
_cache_lock = threading.Lock()

# ══════════════════════════════════════════════════════════════
# DEVICE PROFILE
# ══════════════════════════════════════════════════════════════
DEVICE = {
    "os_info":          "Android OS 9 / API-28 (PI/rel.cjw.20220518.114133)",
    "device_type":      "Handheld",
    "network_provider": "Jio",
    "connection_type":  "WIFI",
    "screen_width":     1080,
    "screen_height":    2340,
    "dpi":              "480",
    "cpu_info":         "ARMv8 VFPv3 NEON VMH | 2400 | 8",
    "total_ram":        5951,
    "gpu_name":         "Adreno (TM) 640",
    "gpu_version":      "OpenGL ES 3.2",
    "user_id":          "Google|74b585a9-0268-4ad3-8f36-ef41d2e53610",
    "ip_address":       "172.190.111.97",
    "language":         "en",
    "os_architecture":  "arm64-v8a",
    "graphics_backend": "Vulkan",
    "marketplace":      "googleplay",
}
PLATFORM_ANDROID = 3


# ══════════════════════════════════════════════════════════════
# REMOTE UID SYNC (background thread)
# ══════════════════════════════════════════════════════════════

def _fetch_raw_uids(server_name: str, url: str) -> set:
    """Fetch plain-text UID list from remote server."""
    try:
        r = req_lib.get(url, timeout=10, proxies={"http": None, "https": None})
        r.raise_for_status()
        uids = {line.strip() for line in r.text.splitlines() if line.strip().isdigit()}
        Console.success(f"UID sync [{server_name}] → {len(uids)} UIDs")
        return uids
    except Exception as e:
        Console.error(f"UID sync [{server_name}] FAILED", exception=str(e))
        return set()


def _sync_loop():
    """Background thread: syncs remote UID servers every UID_SYNC_INTERVAL seconds."""
    while True:
        for name, url in UID_SERVERS.items():
            uids = _fetch_raw_uids(name, url)
            if uids:
                with _cache_lock:
                    _uid_cache[name] = uids
        time.sleep(UID_SYNC_INTERVAL)


def start_uid_sync():
    t = threading.Thread(target=_sync_loop, daemon=True, name="UID-Sync")
    t.start()
    Console.success("UID sync thread started (spectre + sigma)")


# ══════════════════════════════════════════════════════════════
# UID CHECK — 4-source priority chain
# ══════════════════════════════════════════════════════════════


def _check_remote_cache(uid: str) -> bool:
    """Check UID against in-memory cache from spectre/sigma servers."""
    with _cache_lock:
        for name, uids in _uid_cache.items():
            if uid in uids:
                Console.success(f"UID {uid} found in remote cache [{name}]")
                return True
    return False


def _check_local_files(uid: str) -> bool:
    """Check UID against local whitelist JSON files."""
    now = int(time.time())
    try:
        wp = Path(os.path.join(BASE_DIR, "whitelist.json"))
        if wp.exists():
            data = json.loads(wp.read_text(encoding="utf-8"))
            if isinstance(data, list):
                if uid in [str(u) for u in data]:
                    return True
            elif isinstance(data, dict):
                ud = data.get("whitelisted_uids", data)
                if uid in ud:
                    entry = ud[uid]
                    expiry = int(entry.get("expiry", 0)) if isinstance(entry, dict) else int(entry)
                    return now < expiry
    except Exception:
        pass

    for sf in ["whitelist_ind.json", "whitelist_pk.json", "whitelist_bd.json",
               "whitelist_sg.json",  "whitelist_th.json",  "whitelist_id.json",
               "whitelist_me.json",  "whitelist_br.json",  "whitelist_na.json",
               "whitelist_us.json",  "whitelist_ru.json",  "whitelist_sac.json",
               "whitelist_europe.json", "whitelist_vn.json"]:
        try:
            fp = Path(os.path.join(BASE_DIR, sf))
            if fp.exists():
                sd = json.loads(fp.read_text(encoding="utf-8"))
                if isinstance(sd, dict) and uid in sd:
                    ed = sd[uid]
                    ts = int(ed.get("expiry", 0)) if isinstance(ed, dict) else int(float(ed))
                    return now < ts
        except Exception:
            continue
    return False


def checkUID(uid: str) -> bool:
    """
    UID check — 3-source priority:
      1. spectre.dpdns.org   (remote raw list — synced every 60s)
      2. sigma.vexanode.cloud (remote raw list backup)
      3. Local whitelist.json / whitelist_*.json (offline fallback)
    """
    uid = str(uid).strip()

    # 1 & 2. Remote UID server cache (spectre + sigma, synced in background)
    if _check_remote_cache(uid):
        Console.success(f"UID {uid} -> ALLOWED (remote server)")
        return True

    # 3. Local whitelist JSON files (offline fallback)
    if _check_local_files(uid):
        Console.success(f"UID {uid} -> ALLOWED (local whitelist)")
        return True

    Console.error(f"UID {uid} -> BLOCKED")
    return False


def autoAddUID(uid: str):
    """Cache allowed UID to whitelist.json so offline fallback works."""
    try:
        wp = Path(os.path.join(BASE_DIR, "whitelist.json"))
        data = json.loads(wp.read_text(encoding="utf-8")) if wp.exists() else {
            "auto_whitelist_duration_days": 1, "whitelisted_uids": {}
        }
        if "whitelisted_uids" not in data:
            data["whitelisted_uids"] = {}
        expiry = int(time.time() + 86400)  # cache for 1 day
        if uid not in data["whitelisted_uids"]:
            data["whitelisted_uids"][uid] = expiry
            wp.write_text(json.dumps(data, indent=4, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


# ══════════════════════════════════════════════════════════════
# BUILD MOBILE PROTO
# ══════════════════════════════════════════════════════════════

def buildMobileProto(access_token, open_id,
                     game_version="1.120.3",
                     game_name="free fire",
                     timestamp=None):
    if not timestamp:
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())
    gd = my_pb2.GameData()
    gd.access_token     = access_token
    gd.open_id          = open_id
    gd.platform_type    = PLATFORM_ANDROID
    gd.field_99         = str(PLATFORM_ANDROID)
    gd.field_100        = str(PLATFORM_ANDROID)
    gd.timestamp        = timestamp
    gd.game_name        = game_name
    gd.game_version     = 1
    gd.version_code     = game_version
    gd.os_info          = DEVICE["os_info"]
    gd.device_type      = DEVICE["device_type"]
    gd.network_provider = DEVICE["network_provider"]
    gd.connection_type  = DEVICE["connection_type"]
    gd.screen_width     = DEVICE["screen_width"]
    gd.screen_height    = DEVICE["screen_height"]
    gd.dpi              = DEVICE["dpi"]
    gd.cpu_info         = DEVICE["cpu_info"]
    gd.total_ram        = DEVICE["total_ram"]
    gd.gpu_name         = DEVICE["gpu_name"]
    gd.gpu_version      = DEVICE["gpu_version"]
    gd.user_id          = DEVICE["user_id"]
    gd.ip_address       = DEVICE["ip_address"]
    gd.language         = DEVICE["language"]
    gd.os_architecture  = DEVICE["os_architecture"]
    gd.graphics_backend = DEVICE["graphics_backend"]
    gd.marketplace      = DEVICE["marketplace"]
    return gd.SerializeToString()


def extractUID(resp_bytes):
    try:
        msg = output_pb2.Garena_420()
        msg.ParseFromString(resp_bytes)
        if msg.account_id:
            return str(msg.account_id)
    except Exception:
        pass
    try:
        fields = json.loads(get_available_room(resp_bytes.hex()))
        for f in ["1", "2", "3"]:
            if f in fields and isinstance(fields[f], dict):
                v = str(fields[f].get("data", ""))
                if v.isdigit() and len(v) > 5:
                    return v
    except Exception:
        pass
    return None


# ══════════════════════════════════════════════════════════════
# JWT API HELPERS (inline — no Flask server needed)
# ══════════════════════════════════════════════════════════════

AES_KEY = b'Yg&tc%DEuh6%Zc^8'
AES_IV  = b'6oyZDr22E3ychjM%'


def _encrypt_proto(plaintext: bytes) -> bytes:
    from Crypto.Cipher import AES
    from Crypto.Util.Padding import pad
    cipher = AES.new(AES_KEY, AES.MODE_CBC, AES_IV)
    return cipher.encrypt(pad(plaintext, AES.block_size))


def _fetch_open_id(access_token: str):
    try:
        res = req_lib.get(
            "https://prod-api.reward.ff.garena.com/redemption/api/auth/inspect_token/",
            headers={"access-token": access_token,
                     "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36"},
            timeout=5
        )
        uid = res.json().get("uid")
        if not uid:
            return None, "UID not found in inspect_token"
        oid_res = req_lib.post(
            "https://shop2game.com/api/auth/player_id_login",
            headers={"Content-Type": "application/json",
                     "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36"},
            json={"app_id": 100067, "login_id": str(uid)},
            timeout=5
        )
        open_id = oid_res.json().get("open_id")
        return (open_id, None) if open_id else (None, "open_id not found")
    except Exception as e:
        return None, str(e)


def _do_jwt_login(access_token: str, open_id: str) -> dict:
    for platform in [3, 8, 4, 6]:
        try:
            gd = my_pb2.GameData()
            gd.timestamp        = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())
            gd.game_name        = "free fire"
            gd.game_version     = 1
            gd.version_code     = "1.108.3"
            gd.os_info          = DEVICE["os_info"]
            gd.device_type      = DEVICE["device_type"]
            gd.network_provider = DEVICE["network_provider"]
            gd.connection_type  = DEVICE["connection_type"]
            gd.screen_width     = DEVICE["screen_width"]
            gd.screen_height    = DEVICE["screen_height"]
            gd.dpi              = DEVICE["dpi"]
            gd.cpu_info         = DEVICE["cpu_info"]
            gd.total_ram        = DEVICE["total_ram"]
            gd.gpu_name         = DEVICE["gpu_name"]
            gd.gpu_version      = DEVICE["gpu_version"]
            gd.user_id          = DEVICE["user_id"]
            gd.ip_address       = DEVICE["ip_address"]
            gd.language         = DEVICE["language"]
            gd.open_id          = open_id
            gd.access_token     = access_token
            gd.platform_type    = platform
            gd.field_99         = str(platform)
            gd.field_100        = str(platform)

            enc  = _encrypt_proto(gd.SerializeToString())
            resp = req_lib.post(
                "https://loginbp.ggblueshark.com/MajorLogin",
                data=enc,
                headers={
                    "User-Agent":      "Dalvik/2.1.0 (Linux; U; Android 9; ASUS_Z01QD Build/PI)",
                    "Content-Type":    "application/octet-stream",
                    "X-Unity-Version": "2018.4.11f1",
                    "ReleaseVersion":  "OB51",
                },
                verify=False, timeout=5
            )
            if resp.status_code != 200:
                continue

            msg = output_pb2.Garena_420()
            msg.ParseFromString(resp.content)
            if not msg.token:
                continue

            import jwt as pyjwt
            try:
                decoded = pyjwt.decode(msg.token, options={"verify_signature": False})
            except Exception:
                decoded = {}

            return {
                "status":        "success",
                "platform_used": platform,
                "account_id":    decoded.get("account_id") or msg.account_id,
                "account_name":  decoded.get("nickname"),
                "region":        decoded.get("lock_region") or msg.region,
                "open_id":       open_id,
                "access_token":  access_token,
                "token":         msg.token,
            }
        except Exception:
            continue
    return {"status": "error", "message": "No valid platform found"}


# ══════════════════════════════════════════════════════════════
# MITMPROXY ADDON
# ══════════════════════════════════════════════════════════════

class Sage666:

    def _patch(self, flow: http.HTTPFlow, label: str):
        try:
            fields = json.loads(get_available_room(aes_decrypt(flow.request.content.hex()).hex()))
            at  = str(fields["29"]["data"]) if "29" in fields and isinstance(fields["29"], dict) else None
            oid = str(fields["22"]["data"]) if "22" in fields and isinstance(fields["22"], dict) else None
            gv  = str(fields["7"]["data"])  if "7"  in fields and isinstance(fields["7"],  dict) else "1.120.3"
            gn  = str(fields["4"]["data"])  if "4"  in fields and isinstance(fields["4"],  dict) else "free fire"
            ts  = str(fields["3"]["data"])  if "3"  in fields and isinstance(fields["3"],  dict) else None
            if not at or not oid:
                Console.error(f"{label}: missing tokens — pass-through")
                return
            flow.request.content = bytes.fromhex(encrypt_api(buildMobileProto(at, oid, gv, gn, ts)))
            Console.success(f"{label} patched → platform=3 (Android)")
        except Exception as e:
            Console.error(f"{label} patch failed", exception=str(e))

    def _handle_access_jwt(self, flow: http.HTTPFlow):
        params       = dict(flow.request.query)
        access_token = params.get("access_token", "")
        open_id      = params.get("open_id") or params.get("provided_open_id")

        if not access_token:
            flow.response = http.Response.make(400,
                json.dumps({"message": "missing access_token"}).encode(),
                {"Content-Type": "application/json"})
            return

        if not open_id:
            open_id, err = _fetch_open_id(access_token)
            if err:
                flow.response = http.Response.make(400,
                    json.dumps({"message": err}).encode(),
                    {"Content-Type": "application/json"})
                return

        result = _do_jwt_login(access_token, open_id)
        flow.response = http.Response.make(
            200 if result.get("status") == "success" else 400,
            json.dumps(result).encode(),
            {"Content-Type": "application/json"}
        )
        Console.success(f"JWT /access-jwt → UID {result.get('account_id', '?')}")

    def _handle_token(self, flow: http.HTTPFlow):
        params   = dict(flow.request.query)
        uid      = params.get("uid", "")
        password = params.get("password", "")

        if not uid or not password:
            flow.response = http.Response.make(400,
                json.dumps({"message": "missing uid or password"}).encode(),
                {"Content-Type": "application/json"})
            return
        try:
            oauth = req_lib.post(
                "https://100067.connect.garena.com/oauth/guest/token/grant",
                data={
                    "uid": uid, "password": password,
                    "response_type": "token", "client_type": "2",
                    "client_secret": "2ee44819e9b4598845141067b281621874d0d5d7af9d8f7e00c1e54715b7d1e3",
                    "client_id": "100067",
                },
                headers={"User-Agent": "GarenaMSDK/4.0.19P9(SM-M526B ;Android 13;pt;BR;)"},
                timeout=5
            )
            od = oauth.json()
            if "access_token" not in od:
                flow.response = http.Response.make(400,
                    json.dumps(od).encode(), {"Content-Type": "application/json"})
                return
            result = _do_jwt_login(od["access_token"], od.get("open_id", ""))
            flow.response = http.Response.make(
                200 if result.get("status") == "success" else 400,
                json.dumps(result).encode(), {"Content-Type": "application/json"})
        except Exception as e:
            flow.response = http.Response.make(500,
                json.dumps({"message": str(e)}).encode(),
                {"Content-Type": "application/json"})

    def request(self, flow: http.HTTPFlow):
        path = flow.request.path

        # Prevent infinite loops if mitmproxy intercepts its own traffic
        if flow.request.host == "127.0.0.1" or flow.request.host == "localhost":
            pass
        else:
            # Route Web Panel traffic to local Flask server
            admin_routes = ["/", "/dashboard", "/login", "/logout", "/add_uid", "/remove_uid", "/static", "/favicon.ico", "/api"]
            if any(path == r or path.startswith(r + "/") or path.startswith(r + "?") for r in admin_routes):
                if "freefire" not in flow.request.host.lower() and "garena" not in flow.request.host.lower():
                    flow.request.host = "127.0.0.1"
                    flow.request.port = 5000
                    flow.request.scheme = "http"
                    if "Host" in flow.request.headers:
                        flow.request.headers["Host"] = "127.0.0.1:5000"
                    return

        if path.startswith("/access-jwt"):
            self._handle_access_jwt(flow)
            return
        if path.startswith("/token"):
            self._handle_token(flow)
            return

        if flow.request.method.upper() != "POST":
            return
        if "/MajorLogin"    in path: self._patch(flow, "MajorLogin")
        elif "/GetLoginData" in path: self._patch(flow, "GetLoginData")

    def response(self, flow: http.HTTPFlow):
        if flow.request.method.upper() != "POST":
            return
        if "majorlogin" not in flow.request.path.lower():
            return
        try:
            uid = extractUID(flow.response.content)
            if not uid:
                Console.error("No UID in response")
                return

            Console.info(f"Login UID: {uid}")

            if not checkUID(uid):
                Console.error(f"UID {uid} BLOCKED")
                msg = (
                    f"[44A2FF]⧉───────────────────────────────────────────────⧉\n"
                    f"[44A2FF]⟡  STATUS  :   [FF0000] UID BYPASS ACCESS DENIED\n"
                    f"[44A2FF]⟡  UID     :   [FFFFFF]{uid}\n"
                    f"[44A2FF]⟡  TIME    :   [FFFFFF]{time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime())}\n"
                    f"[44A2FF]⟡  DEV     :   [FFFFFF] UID BYPASS PRIVATE SYSTEM\n"
                    f"[44A2FF]⧉───────────────────────────────────────────────⧉\n"
                ).encode()
                flow.response.content     = msg
                flow.response.status_code = 500
                return

            Console.success(f"UID {uid} ALLOWED")
            autoAddUID(uid)   # cache locally for offline fallback

        except Exception as e:
            Console.error("Response handler error", exception=str(e))


addons = [Sage666()]

# Start UID background sync when addon loads
start_uid_sync()
