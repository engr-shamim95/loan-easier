import sys
import uvicorn
import socket
import threading
import webbrowser
import time
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import HOST, PORT

def get_available_port(start_port=8000):
    port = start_port
    while True:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex((HOST, port)) != 0:
                return port
        port += 1

def open_browser(port):
    time.sleep(2)
    webbrowser.open(f"http://{HOST}:{port}")

def main():
    actual_port = get_available_port(PORT)
    print(f"Starting Loan Easier server on http://{HOST}:{actual_port}")
    
    # Start browser in a background thread
    threading.Thread(target=open_browser, args=(actual_port,), daemon=True).start()
    
    uvicorn.run(
        "src.api.app:app",
        host=HOST,
        port=actual_port,
        reload=False,
        log_level="info",
    )

if __name__ == "__main__":
    main()
