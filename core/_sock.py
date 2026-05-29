import asyncio
import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BASE_DIR)
sys.path.insert(0, ROOT_DIR)

from src.utils.console import Console

class SockHandler:
    """
    Advanced Socket Handler for UID BYPASS Bypass Proxy.
    Handles low-level data transfer and preamble parsing.
    """
    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        self.reader = reader
        self.writer = writer
        self.peer_name = writer.get_extra_info('peername')

    async def read_preamble(self):
        """
        Reads the 6-byte preamble containing the original target IP and Port.
        Format: [4 bytes IP][2 bytes Port (Big Endian)]
        """
        try:
            data = await self.reader.readexactly(6)
            ip = ".".join(map(str, data[:4]))
            port = int.from_bytes(data[4:], byteorder='big')
            return ip, port
        except asyncio.IncompleteReadError:
            return None, None
        except Exception as e:
            Console.error(f"Preamble read error from {self.peer_name}", exception=str(e))
            return None, None

    async def pipe(self, destination: 'SockHandler'):
        """
        Pipes data from this socket to the destination socket.
        """
        try:
            while True:
                data = await self.reader.read(8192)
                if not data:
                    break
                
                # Here we could inject packet modification logic
                # For UID BYPASS Bypass, we might want to patch specific matchmaking bytes
                
                destination.writer.write(data)
                await destination.writer.drain()
        except (ConnectionResetError, BrokenPipeError, asyncio.CancelledError):
            pass
        except Exception as e:
            Console.error(f"Pipe error: {self.peer_name} -> {destination.peer_name}", exception=str(e))
        finally:
            await destination.close()

    async def close(self):
        """
        Gracefully closes the socket.
        """
        try:
            if not self.writer.is_closing():
                self.writer.close()
                await self.writer.wait_closed()
        except:
            pass
