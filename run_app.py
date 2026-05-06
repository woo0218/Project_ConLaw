import multiprocessing
import os
import socket
import sys
import threading
import time
import urllib.request
import webbrowser


HOST = "127.0.0.1"
PORT = 8000
APP_URL = f"http://{HOST}:{PORT}"
HEALTH_URL = f"{APP_URL}/health"


def get_runtime_base() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def create_writable_directories(runtime_base: str) -> None:
    for relative_path in ("data", os.path.join("data", "templates"), "outputs", "static"):
        os.makedirs(os.path.join(runtime_base, relative_path), exist_ok=True)


def ensure_port_available(host: str, port: int) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(1)
        if sock.connect_ex((host, port)) == 0:
            raise RuntimeError(f"{host}:{port} 포트가 이미 사용 중입니다. 실행 중인 프로그램을 종료한 후 다시 시도하십시오.")


def start_server() -> None:
    import uvicorn
    import app.main

    uvicorn.run(app.main.app, host=HOST, port=PORT, log_level="warning")


def wait_until_ready() -> None:
    for _ in range(30):
        try:
            with urllib.request.urlopen(HEALTH_URL, timeout=1) as response:
                if response.status == 200:
                    return
        except Exception:
            time.sleep(0.5)
    raise RuntimeError("서버가 준비되지 않았습니다. 잠시 후 다시 실행하십시오.")


def main() -> None:
    runtime_base = get_runtime_base()
    os.chdir(runtime_base)
    create_writable_directories(runtime_base)
    ensure_port_available(HOST, PORT)

    server_thread = threading.Thread(target=start_server, daemon=True)
    server_thread.start()

    wait_until_ready()
    webbrowser.open(APP_URL)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        return


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
