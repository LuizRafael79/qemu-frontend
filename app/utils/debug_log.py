import os
from datetime import datetime

LOG_FILE = os.path.expanduser("~/.cache/qemu_frontend/debug.log")

def debug_log(msg: str):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, "a") as f:
        f.write(f"[{timestamp}] {msg}\n")
