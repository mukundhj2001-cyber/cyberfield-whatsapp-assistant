import os, socket, subprocess, sys, time, tempfile
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
os.environ["DB_PATH"] = str(Path(tempfile.mkdtemp()) / "test.db")
os.environ["WHATSAPP_RETRY_BASE_DELAY"] = "0"
for k in ("LLM_API_KEY", "WHATSAPP_TOKEN", "WHATSAPP_PHONE_NUMBER_ID", "WHATSAPP_APP_SECRET", "ADMIN_USERNAME", "ADMIN_PASSWORD",
          "STT_API_KEY", "RAZORPAY_KEY_ID", "RAZORPAY_KEY_SECRET", "RAZORPAY_WEBHOOK_SECRET", "SESSION_SECRET"):
    os.environ.pop(k, None)


@pytest.fixture()
def client():
    from fastapi.testclient import TestClient
    from app import main, seed
    with TestClient(main.app) as c:
        seed.seed(force=True)
        assert c.post("/api/auth/login", json={"username": "admin", "password": "cyberfield"}).status_code == 200
        yield c


@pytest.fixture()
def anon():
    from fastapi.testclient import TestClient
    from app import main
    with TestClient(main.app) as c:
        yield c


@pytest.fixture(scope="session")
def live_server():
    """Run the real app (with built frontend) on a free port for Playwright."""
    s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
    env = {**os.environ, "DB_PATH": str(Path(tempfile.mkdtemp()) / "e2e.db")}
    p = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--port", str(port)], cwd=ROOT / "backend", env=env,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    url = f"http://127.0.0.1:{port}"
    import httpx
    for _ in range(60):
        try:
            httpx.get(url + "/api/health"); break
        except Exception:
            time.sleep(0.25)
    yield url
    p.terminate()
