
import hashlib
import hmac
import socket
import struct
import time
from pathlib import Path

# Must exactly match server.py.
SHARED_SECRET = b"25085944e0ac2d2b41c5daf5985640ef03f9b22f64d0a2df6e3a2ee79859803c"

DISCOVERY_PORT = 5002
DISCOVERY_MESSAGE = b"TXTFILE_DISCOVER_V1"
RESPONSE_PREFIX = b"TXTFILE_SERVER_V1:"
MAX_FILE_SIZE = 5 * 1024 * 1024

# Change this to your text document's path.
FILE_TO_SEND = Path.home() / "Desktop" / "Log_file.txt"


def receive_exact(conn, size):
    data = bytearray()
    while len(data) < size:
        chunk = conn.recv(size - len(data))
        if not chunk:
            raise ConnectionError("Connection closed unexpectedly.")
        data.extend(chunk)
    return bytes(data)


def discover_server(timeout=30):
    print("Searching for the receiving laptop...")

    deadline = time.monotonic() + timeout

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.settimeout(1)

        while time.monotonic() < deadline:
            sock.sendto(
                DISCOVERY_MESSAGE,
                ("255.255.255.255", DISCOVERY_PORT)
            )

            try:
                response, address = sock.recvfrom(1024)

                if response.startswith(RESPONSE_PREFIX):
                    port = int(response[len(RESPONSE_PREFIX):])
                    print(f"Found server at {address[0]}:{port}")
                    return address[0], port

            except socket.timeout:
                continue

    raise TimeoutError(
        "Server not found. Check both laptops are on the same Wi-Fi."
    )


def send_file(host, port):
    if not FILE_TO_SEND.is_file():
        raise FileNotFoundError(f"Text file not found: {FILE_TO_SEND}")

    if FILE_TO_SEND.suffix.lower() != ".txt":
        raise ValueError("Only .txt files are allowed.")

    file_size = FILE_TO_SEND.stat().st_size
    if file_size > MAX_FILE_SIZE:
        raise ValueError("File exceeds the 5 MB limit.")

    filename = FILE_TO_SEND.name.encode("utf-8")
    if len(filename) > 255:
        raise ValueError("Filename is too long.")

    with socket.create_connection((host, port), timeout=15) as conn:
        conn.settimeout(30)

        # Authenticate by responding to the server's random challenge.
        nonce = receive_exact(conn, 32)
        response = hmac.new(
            SHARED_SECRET, nonce, hashlib.sha256
        ).digest()
        conn.sendall(response)

        if receive_exact(conn, 1) != b"\x01":
            raise PermissionError("Server rejected authentication.")

        # Send filename length, filename, file size, then file contents.
        conn.sendall(struct.pack("!H", len(filename)))
        conn.sendall(filename)
        conn.sendall(struct.pack("!Q", file_size))

        with FILE_TO_SEND.open("rb") as source:
            while True:
                chunk = source.read(65536)
                if not chunk:
                    break
                conn.sendall(chunk)

        if receive_exact(conn, 1) != b"\x01":
            raise RuntimeError("Server did not confirm the transfer.")

    print(f"Successfully sent: {FILE_TO_SEND.name}")


def main():
    if SHARED_SECRET == b"REPLACE_WITH_A_LONG_RANDOM_SECRET_HERE":
        raise SystemExit("Set SHARED_SECRET in sender.py first.")

    host, port = discover_server()
    send_file(host, port)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, PermissionError, TimeoutError) as error:
        print(f"Transfer failed: {error}")
    except KeyboardInterrupt:
        print("\nSender stopped.")
