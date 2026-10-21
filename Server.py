
import hashlib
import hmac
import os
import secrets
import socket
import struct
import threading
from pathlib import Path

# Replace this with the SAME random secret in sender.py.
SHARED_SECRET = b"25085944e0ac2d2b41c5daf5985640ef03f9b22f64d0a2df6e3a2ee79859803c"

DISCOVERY_PORT = 5002
TRANSFER_PORT = 5001
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB
DISCOVERY_MESSAGE = b"TXTFILE_DISCOVER_V1"
RESPONSE_PREFIX = b"TXTFILE_SERVER_V1:"


def receive_exact(conn, size):
    data = bytearray()
    while len(data) < size:
        chunk = conn.recv(size - len(data))
        if not chunk:
            raise ConnectionError("Connection closed unexpectedly.")
        data.extend(chunk)
    return bytes(data)


def discovery_listener():
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("0.0.0.0", DISCOVERY_PORT))
        print(f"Discovery listening on UDP port {DISCOVERY_PORT}")

        while True:
            message, address = sock.recvfrom(1024)

            if message == DISCOVERY_MESSAGE:
                response = RESPONSE_PREFIX + str(TRANSFER_PORT).encode()
                sock.sendto(response, address)


def handle_sender(conn, address):
    with conn:
        conn.settimeout(30)
        print(f"Connection from {address[0]}")

        # Challenge-response authentication: never send the secret itself.
        nonce = secrets.token_bytes(32)
        conn.sendall(nonce)

        received_mac = receive_exact(conn, 32)
        expected_mac = hmac.new(
            SHARED_SECRET, nonce, hashlib.sha256
        ).digest()

        if not hmac.compare_digest(received_mac, expected_mac):
            conn.sendall(b"\x00")
            print("Authentication failed.")
            return

        conn.sendall(b"\x01")

        name_length = struct.unpack("!H", receive_exact(conn, 2))[0]
        if not 1 <= name_length <= 255:
            raise ValueError("Invalid filename length.")

        filename = receive_exact(conn, name_length).decode("utf-8")
        file_size = struct.unpack("!Q", receive_exact(conn, 8))[0]

        if (
            Path(filename).name != filename
            or not filename.lower().endswith(".txt")
            or file_size > MAX_FILE_SIZE
        ):
            raise ValueError("Invalid filename or file size.")

        desktop = Path.home() / "Desktop"
        desktop.mkdir(parents=True, exist_ok=True)

        # Never overwrite an existing file.
        destination = desktop / filename
        if destination.exists():
            destination = desktop / f"{destination.stem}_{secrets.token_hex(4)}.txt"

        remaining = file_size

        with destination.open("xb") as output:
            while remaining:
                chunk = receive_exact(conn, min(65536, remaining))
                output.write(chunk)
                remaining -= len(chunk)

        conn.sendall(b"\x01")
        print(f"Saved {file_size} bytes to: {destination}")

    # Only accepts one file per connection.


def main():
    if SHARED_SECRET == b"REPLACE_WITH_A_LONG_RANDOM_SECRET_HERE":
        raise SystemExit("Set SHARED_SECRET in server.py first.")

    threading.Thread(target=discovery_listener, daemon=True).start()

    print("Text-file receiver is running.")
    print("Keep this window open.")

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(("0.0.0.0", TRANSFER_PORT))
        server.listen()

        while True:
            conn, address = server.accept()
            try:
                handle_sender(conn, address)
            except (OSError, ValueError, UnicodeError) as error:
                print(f"Transfer failed: {error}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nServer stopped.")
