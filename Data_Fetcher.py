
import getpass
import platform
import socket
import time
from datetime import datetime
import subprocess
import re
import asyncio
import os
import sys

from bleak import BleakScanner
import psutil

log_file = open(os.path.join(os.path.expanduser("~"), "Desktop", "Log_File.txt"), "a", encoding="utf-8")
sys.stdout = log_file
sys.stderr = log_file

async def enable_bluetooth():
    try:
        from winrt.windows.devices.radios import (
            Radio, RadioKind, RadioState
        )

        radios = await Radio.get_radios_async()
        bluetooth_found = False

        for radio in radios:
            if radio.kind == RadioKind.BLUETOOTH:
                bluetooth_found = True
                print(f"Bluetooth radio: {radio.state}")

                if radio.state != RadioState.ON:
                    result = await radio.set_state_async(
                        RadioState.ON
                    )
                    print(f"Enable result: {result}")
                    print(f"New state: {radio.state}")
                else:
                    print("Bluetooth is already on.")

        if not bluetooth_found:
            print("No Bluetooth radio detected by Windows.")

    except Exception as error:
        print(f"Could not enable Bluetooth: {error}")


def format_bytes(value: int | float) -> str:
    size = float(value)

    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size:.1f} {unit}"
        size /= 1024

    return f"{size:.1f} TB"


def format_uptime(seconds: float) -> str:
    days, remainder = divmod(int(seconds), 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes = remainder // 60
    return f"{days}d {hours}h {minutes}m"


def main() -> None:
    print("\n=== Local Device Inventory ===")
    print(f"Computer name: {socket.gethostname()}")
    print(f"Current account: {getpass.getuser()}")
    print(f"Operating system: {platform.system()} {platform.release()}")
    print(f"OS details: {platform.platform()}")
    print(f"Architecture: {platform.machine()}")
    print(f"Processor: {platform.processor() or 'Not reported'}")
    print(f"Python: {platform.python_version()}")

    boot_time = psutil.boot_time()
    boot_date = datetime.fromtimestamp(boot_time).astimezone()

    print(f"Last boot: {boot_date:%Y-%m-%d %H:%M:%S %Z}")
    print(f"Uptime: {format_uptime(time.time() - boot_time)}")

    print("\n=== Disk Volumes ===")

    for partition in psutil.disk_partitions(all=False):
        try:
            usage = psutil.disk_usage(partition.mountpoint)
        except OSError as exc:
            print(f"{partition.mountpoint}: unavailable ({exc})")
            continue

        print(
            f"{partition.mountpoint} "
            f"[{partition.fstype or 'unknown'}]: "
            f"{format_bytes(usage.free)} free / "
            f"{format_bytes(usage.total)} total "
            f"({usage.percent:.1f}% used)"
        )


def scan_wifi_networks(scan_time=300, interval=5):
    """Repeatedly scan for nearby Wi-Fi networks on Windows."""

    if platform.system() != "Windows":
        print("Wi-Fi scanning requires Windows.")
        return []

    print(f"\n=== Wi-Fi Scan: {scan_time} seconds ===")
    print("Press Ctrl+C to stop early.\n")

    start = time.monotonic()
    networks = {}
    scan_count = 0

    try:
        while time.monotonic() - start < scan_time:
            try:
                result = subprocess.run(
                    [
                        "netsh", "wlan", "show",
                        "networks", "mode=bssid"
                    ],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=20
                )
            except subprocess.TimeoutExpired:
                print("\nWi-Fi scan timed out; retrying.")
                time.sleep(1)
                continue

            scan_count += 1

            if result.returncode == 0:
                current_ssid = None

                for line in result.stdout.splitlines():
                    line = line.strip()

                    ssid_match = re.match(
                        r"SSID\s+\d+\s*:\s*(.*)", line
                    )

                    if ssid_match:
                        ssid = (
                            ssid_match.group(1).strip()
                            or "<Hidden>"
                        )

                        current_ssid = ssid

                        if ssid not in networks:
                            networks[ssid] = {
                                "SSID": ssid,
                                "Authentication": "Unknown",
                                "Security": "Unknown",
                                "Signal": "Unknown",
                                "Radio type": "Unknown",
                                "Channel": "Unknown"
                            }
                        continue

                    if current_ssid is None:
                        continue

                    fields = {
                        "Authentication": r"Authentication\s*:\s*(.*)",
                        "Security": r"Encryption\s*:\s*(.*)",
                        "Signal": r"Signal\s*:\s*(\d+%)",
                        "Radio type": r"Radio type\s*:\s*(.*)",
                        "Channel": r"Channel\s*:\s*(.*)"
                    }

                    network = networks[current_ssid]

                    for key, pattern in fields.items():
                        match = re.match(
                            pattern, line, re.IGNORECASE
                        )

                        if not match:
                            continue

                        value = match.group(1).strip()

                        if key == "Signal":
                            new_signal = re.search(r"\d+", value)
                            old_signal = re.search(
                                r"\d+", network["Signal"]
                            )

                            if new_signal and (
                                not old_signal
                                or int(new_signal.group())
                                > int(old_signal.group())
                            ):
                                network[key] = value
                        else:
                            network[key] = value

            elapsed = int(time.monotonic() - start)

            print(
                f"\rElapsed: {elapsed}/{scan_time}s | "
                f"Scans: {scan_count} | "
                f"Networks: {len(networks)}",
                end="",
                flush=True
            )

            remaining = scan_time - (
                time.monotonic() - start
            )

            if remaining > 0:
                time.sleep(min(interval, remaining))

    except KeyboardInterrupt:
        print("\nWi-Fi scan stopped early.")

    print("\n\n=== Wi-Fi Scan Results ===")

    for number, network in enumerate(
        networks.values(), start=1
    ):
        print(f"\nNetwork {number}")
        print("-" * 35)

        for key, value in network.items():
            print(f"{key}: {value}")

    print(f"\nUnique network names: {len(networks)}")
    print(f"Scan attempts: {scan_count}")

    return list(networks.values())


async def scan_bluetooth_devices(scan_time=10):
    """Scan for nearby discoverable Bluetooth LE devices."""

    print(
        f"\n=== Bluetooth Scan: {scan_time} seconds ==="
    )

    try:
        devices = await BleakScanner.discover(
            timeout=scan_time,
            return_adv=True
        )

        if not devices:
            print("No Bluetooth LE devices found.")
            return []

        results = []

        for address, (device, advertisement) in devices.items():
            info = {
                "Name": (
                    device.name
                    or advertisement.local_name
                    or "Unknown device"
                ),
                "Address": address,
                "RSSI": getattr(
                    advertisement,
                    "rssi",
                    getattr(device, "rssi", "Unknown")
                ),
                "Connectable": getattr(
                    advertisement,
                    "connectable",
                    "Unknown"
                ),
                "Bluetooth services": ", ".join(
                    advertisement.service_uuids or []
                ) or "Not advertised"
            }

            results.append(info)

        for number, device in enumerate(results, start=1):
            print(f"\nDevice {number}")
            print("-" * 40)

            for key, value in device.items():
                print(f"{key}: {value}")

        print(f"\nTotal Bluetooth LE devices: {len(results)}")
        return results

    except Exception as error:
        print(f"Bluetooth scan failed: {error}")
        print("Check that Bluetooth is enabled and available.")
        return []


if __name__ == "__main__":
    try:
        asyncio.run(enable_bluetooth())
        time.sleep(2)

        main()

        # Scan nearby Wi-Fi networks for 15 seconds,
        # repeating the scan approximately every 3 seconds.
        scan_wifi_networks(scan_time=15, interval=3)

        # Scan for nearby Bluetooth LE devices for 10 seconds.
        asyncio.run(scan_bluetooth_devices(scan_time=10))

    except KeyboardInterrupt:
        print("\n\nProgram stopped.")

