import subprocess
import platform
import json
import re
import os
import sys


log_file = open(os.path.join(os.path.expanduser("~"), "Desktop", "Log_File.txt"), "a", encoding="utf-8")
sys.stdout = log_file
sys.stderr = log_file

def get_wifi_passwords():
    # 1. Get all saved Wi-Fi profile names
    meta_data = subprocess.run(
        ["netsh", "wlan", "show", "profiles"],
        capture_output=True,
        text=True,
        errors="replace"
    )
    
    # Extract profile names from the output
    profiles = []
    for line in meta_data.stdout.splitlines():
        if "All User Profile" in line:
            parts = line.split(":", 1)
            if len(parts) > 1:
                profiles.append(parts[1].strip())

    print(f"Found {len(profiles)} saved networks.\n")
    print("Saved Wi-Fi networks & Passwords:\n" + "="*40)

    # 2. Loop through each profile to get its password
    for profile in profiles:
        result = subprocess.run(
            ["netsh", "wlan", "show", "profile", f"name={profile}", "key=clear"],
            capture_output=True,
            text=True,
            errors="replace"
        )
        
        password = "N/A"
        # Look for the password line in this specific profile's output
        for line in result.stdout.splitlines():
            if "Key Content" in line:
                parts = line.split(":", 1)
                if len(parts) > 1:
                    password = parts[1].strip()
                break
                
        print(f"SSID    : {profile}")
        print(f"Password: {password}")
        print("-" * 40)


def get_saved_bluetooth_devices():
    if platform.system() != "Windows":
        print("This script only works on Windows 10/11.")
        return

    powershell_script = r"""
    $devices = Get-PnpDevice -ErrorAction SilentlyContinue |
        Where-Object {
            $_.InstanceId -match '^(BTHENUM|BTHLEDEVICE|BTHLE|BTH)' -and
            $_.FriendlyName
        } |
        Select-Object FriendlyName, Class, Status, Manufacturer, InstanceId

    $devices | ConvertTo-Json -Depth 3 -Compress
    """

    try:
        result = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                powershell_script,
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
            check=True,
        )

        output = result.stdout.strip()

        if not output:
            print("No Bluetooth devices were found by Windows.")
            return

        devices = json.loads(output)

        # PowerShell returns an object instead of a list for one result.
        if isinstance(devices, dict):
            devices = [devices]

        # Remove duplicate entries with the same device ID.
        unique_devices = {}
        for device in devices:
            device_id = device.get("InstanceId", "")
            unique_devices[device_id] = device

        devices = sorted(
            unique_devices.values(),
            key=lambda d: (d.get("FriendlyName") or "").lower()
        )

        print("=" * 65)
        print("       WINDOWS SAVED BLUETOOTH DEVICES")
        print("=" * 65)
        print(f"Devices found: {len(devices)}\n")

        for number, device in enumerate(devices, start=1):
            name = device.get("FriendlyName") or "Unknown"
            device_class = device.get("Class") or "Unknown"
            status = device.get("Status") or "Unknown"
            manufacturer = device.get("Manufacturer") or "Unknown"
            instance_id = device.get("InstanceId") or "Unknown"

            # Extract a Bluetooth address if Windows includes one.
            match = re.search(
                r"DEV_([0-9A-Fa-f]{12})",
                instance_id
            )

            if match:
                raw_address = match.group(1).upper()
                address = ":".join(
                    raw_address[i:i + 2]
                    for i in range(0, 12, 2)
                )
            else:
                address = "Not available"

            # Give a rough device-type estimate based on its name.
            text = f"{name} {device_class}".lower()

            if any(x in text for x in ("headphone", "headset", "earbud")):
                device_type = "Headphones / Headset"
            elif "keyboard" in text:
                device_type = "Keyboard"
            elif "mouse" in text:
                device_type = "Mouse"
            elif any(x in text for x in ("gamepad", "controller", "xbox")):
                device_type = "Game Controller (estimated)"
            elif any(x in text for x in ("phone", "iphone", "android")):
                device_type = "Phone (estimated)"
            elif any(x in text for x in ("speaker", "audio")):
                device_type = "Audio Device"
            else:
                device_type = device_class

            print(f"[{number}] {name}")
            print(f"    Type:       {device_type}")
            print(f"    Status:     {status}")
            print(f"    Address:    {address}")
            print(f"    Manufacturer: {manufacturer}")
            print(f"    Device ID:  {instance_id}")
            print("-" * 65)

        print("\nNote: Windows may retain old device records.")
        print("Status does not necessarily indicate an active connection.")
        print("Some paired devices may not appear in this list.")

    except subprocess.TimeoutExpired:
        print("Timed out while querying Windows Bluetooth devices.")
    except subprocess.CalledProcessError as error:
        print("PowerShell failed to query devices.")
        print(error.stderr or error)
    except json.JSONDecodeError:
        print("Could not read Windows device information.")
    except FileNotFoundError:
        print("Could not find Windows PowerShell.")

if __name__ == "__main__":
    get_wifi_passwords()
    get_saved_bluetooth_devices()
