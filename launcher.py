import os
import sys
import time
import socket
import webbrowser
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import threading

# --- Standard Directory Setup ---
# When running as compiled executable, resolve path relative to exe folder
if getattr(sys, 'frozen', False):
    BASE_DIR = Path(sys._MEIPASS).resolve()
    USER_DIR = Path(sys.executable).parent.resolve()
    sys.path.insert(0, str(BASE_DIR))
    sys.path.insert(0, str(BASE_DIR / "src"))
else:
    BASE_DIR = Path(__file__).resolve().parent
    USER_DIR = BASE_DIR
    sys.path.insert(0, str(BASE_DIR))
    sys.path.insert(0, str(BASE_DIR / "src"))

# Create writeable user folders in application workspace
for folder in ["input", "output", "logs", "knowledge", "config"]:
    (USER_DIR / folder).mkdir(parents=True, exist_ok=True)

# --- Logging Configuration ---
log_file = USER_DIR / "logs" / "launcher.log"
logger = logging.getLogger("AuraLedgerIQLauncher")
logger.setLevel(logging.INFO)
handler = RotatingFileHandler(log_file, maxBytes=10*1024*1024, backupCount=5, encoding="utf-8")
handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] - %(message)s"))
logger.addHandler(handler)

console = logging.StreamHandler()
console.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] - %(message)s"))
logger.addHandler(console)

lock_socket = None


def is_port_in_use(port: int) -> bool:
    """Checks if a local port is already bound."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) == 0


def acquire_instance_lock() -> bool:
    """
    Attempts to bind a local lock socket on port 8505.
    If fails, another instance of the launcher is running.
    """
    global lock_socket
    try:
        lock_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        lock_socket.bind(("127.0.0.1", 8505))
        lock_socket.listen(1)
        return True
    except OSError:
        logger.info("AuraLedgerIQ instance lock already held. Another instance is running.")
        return False


def wait_for_server(port: int, timeout_sec: int = 15) -> bool:
    """Polls the port to check when Streamlit server is ready."""
    start_time = time.time()
    while time.time() - start_time < timeout_sec:
        if is_port_in_use(port):
            return True
        time.sleep(0.1)
    return False


def open_browser_when_ready():
    """Waits for the Streamlit server and opens the browser."""
    logger.info("Browser checker thread started. Waiting for server on 8501...")
    if wait_for_server(8501, timeout_sec=20):
        url = "http://127.0.0.1:8501"
        logger.info(f"Opening browser at: {url}")
        webbrowser.open(url)
    else:
        logger.critical("Server port 8501 did not open within timeout.")
        if sys.platform == "win32":
            import ctypes
            ctypes.windll.user32.MessageBoxW(
                0, 
                "AuraLedgerIQ Streamlit server failed to start within 20 seconds. Please check logs/launcher.log.",
                "Startup Failure", 
                0x10 | 0x0
            )


# --- System Tray Setup ---
def create_tray_icon():
    """Builds and runs the system tray loop using pystray."""
    try:
        import pystray
        from PIL import Image, ImageDraw
    except ImportError:
        logger.error("pystray or Pillow not installed. Skipping system tray setup.")
        return

    def on_open(icon, item):
        webbrowser.open("http://127.0.0.1:8501")

    def on_open_logs(icon, item):
        logs_path = USER_DIR / "logs"
        os.startfile(str(logs_path))

    def on_open_output(icon, item):
        output_path = USER_DIR / "output"
        os.startfile(str(output_path))

    def on_exit(icon, item):
        logger.info("System Tray Exit clicked. Terminating application process.")
        icon.stop()
        if lock_socket:
            lock_socket.close()
        # Force terminate process including main thread Tornado server
        os._exit(0)

    # Generate a professional 64x64 blue icon programmatically
    image = Image.new("RGBA", (64, 64), (255, 255, 255, 0))
    dc = ImageDraw.Draw(image)
    dc.rounded_rectangle([4, 4, 60, 60], radius=12, fill=(31, 78, 121, 255))
    try:
        dc.text((12, 16), "AL", fill=(255, 255, 255, 255), font_size=28)
    except Exception:
        dc.text((16, 20), "AL", fill=(255, 255, 255, 255))

    menu = pystray.Menu(
        pystray.MenuItem("Open AuraLedgerIQ", on_open, default=True),
        pystray.MenuItem("Open Logs Folder", on_open_logs),
        pystray.MenuItem("Open Output Folder", on_open_output),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Exit AuraLedgerIQ", on_exit)
    )

    icon = pystray.Icon("AuraLedgerIQ", image, "AuraLedgerIQ Engine", menu)
    logger.info("Starting System Tray Icon loop...")
    icon.run()


def main():
    logger.info("Initializing AuraLedgerIQ Desktop Launcher...")
    
    # 1. Single Instance Check
    if not acquire_instance_lock():
        if wait_for_server(8501, timeout_sec=3):
            webbrowser.open("http://127.0.0.1:8501")
        sys.exit(0)
        
    # 2. Check if server already running on 8501
    if is_port_in_use(8501):
        logger.info("Streamlit server already running on port 8501.")
        webbrowser.open("http://127.0.0.1:8501")
        sys.exit(0)

    # 3. Start Browser Checker Thread
    checker = threading.Thread(target=open_browser_when_ready, daemon=True)
    checker.start()

    # 4. Start System Tray Icon in a Background Thread
    tray = threading.Thread(target=create_tray_icon, daemon=True)
    tray.start()

    # 5. Bootstrap Streamlit in the Main Thread
    # Locate app.py in bundled resource dir (sys._MEIPASS) or local dir
    if getattr(sys, 'frozen', False):
        app_path = Path(sys._MEIPASS) / "app.py"
    else:
        app_path = BASE_DIR / "app.py"

    logger.info(f"Bootstrapping Streamlit programmatically with script: {app_path}")
    try:
        from streamlit.web import bootstrap
        
        flag_options = {
            "server.port": 8501,
            "server.address": "127.0.0.1",
            "server.headless": True,
            "browser.gatherUsageStats": False
        }
        
        # Run programmatic server
        bootstrap.run(str(app_path), False, [], flag_options)
        
    except Exception as e:
        logger.critical(f"Critical error bootstrapping Streamlit server: {e}")
        if sys.platform == "win32":
            import ctypes
            ctypes.windll.user32.MessageBoxW(
                0, 
                f"Critical error bootstrapping Streamlit server: {e}", 
                "Bootstrap Failure", 
                0x10 | 0x0
            )
        sys.exit(1)


if __name__ == "__main__":
    main()
