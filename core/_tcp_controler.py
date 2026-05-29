import asyncio
import sys
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BASE_DIR)
sys.path.insert(0, ROOT_DIR)

from _sock import SockHandler
from src.utils.console import Console

class TCPController:
    """
    TCP Controller.
    Listens for redirected connections from UIDBypassDll and forwards them to game servers.
    """
    def __init__(self, host='0.0.0.0', port=19112):
        self.host = host
        self.port = port
        self.active_connections = 0

    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """
        Handles incoming connection from the DLL.
        """
        self.active_connections += 1
        client = SockHandler(reader, writer)
        Console.info(f"New client connected: {client.peer_name} (Active: {self.active_connections})")

        try:
            # 1. Read preamble to find where the game was actually trying to go
            target_ip, target_port = await client.read_preamble()
            
            if not target_ip or not target_port:
                Console.error(f"Invalid preamble from {client.peer_name}. Closing.")
                await client.close()
                return

            Console.success(f"Redirection Request: {client.peer_name} -> {target_ip}:{target_port}")

            # 2. Connect to the real game server
            try:
                remote_reader, remote_writer = await asyncio.open_connection(target_ip, target_port)
                remote = SockHandler(remote_reader, remote_writer)
                Console.info(f"Connected to game server {target_ip}:{target_port}")
            except Exception as e:
                Console.error(f"Failed to connect to game server {target_ip}:{target_port}", exception=str(e))
                await client.close()
                return

            # Instruction 42: "Proxy server matchmaking patch karta hai (is_in_emulator_pool=false)"
            
            await asyncio.gather(
                client.pipe(remote),
                remote.pipe(client),
                return_exceptions=True
            )

        except Exception as e:
            Console.error(f"TCP Controller exception for {client.peer_name}", exception=str(e))
        finally:
            self.active_connections -= 1
            await client.close()
            Console.info(f"Connection closed: {client.peer_name} (Active: {self.active_connections})")

    async def start(self):
        """
        Starts the TCP Proxy Server.
        """
        try:
            server = await asyncio.start_server(self.handle_client, self.host, self.port)
            addr = server.sockets[0].getsockname()
            
            Console.divider("UID BYPASS TCP CONTROL CENTER")
            Console.success(f"Server Status: ONLINE")
            Console.info(f"Listening on : {addr[0]}:{addr[1]}")
            Console.info(f"Ready for DLL Redirections...")
            Console.divider("")

            async with server:
                await server.serve_forever()
        except Exception as e:
            Console.error("Failed to start TCP Controller", exception=str(e))

if __name__ == "__main__":
    # Load config or use defaults
    PORT = 19112 # Should match FALLBACK_PROXY_PORT in DLL
    controller = TCPController(port=PORT)
    
    try:
        asyncio.run(controller.start())
    except KeyboardInterrupt:
        Console.info("TCP Controller stopped by user.")
