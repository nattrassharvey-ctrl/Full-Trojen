import os
import time

# Get the path to the user's desktop
desktop_path = os.path.expanduser("~/Desktop")
file_path = os.path.join(desktop_path, "Log_File.txt")

if os.path.exists(file_path):
    os.remove(file_path)
    print("The file has been deleted.")


print(f"Created file at: {file_path}")

quit()