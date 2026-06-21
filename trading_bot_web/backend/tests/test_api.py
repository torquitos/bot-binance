import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest
from dotenv import load_dotenv

BASE = Path(__file__).resolve().parent.parent
load_dotenv(BASE / ".env")

from app import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


# Fixture that sets API_KEY for auth tests
@pytest.fixture
def auth_client():
    app.config["TESTING"] = True
    with patch.dict(os.environ, {"API_KEY": "test-key-123"}):
        with app.test_client() as c:
            yield c


def test_health(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ok"] is True


def test_state(client):
    resp = client.get("/api/state")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ok"] is True
    assert "symbol" in data["state"]


def test_strategies(client):
    resp = client.get("/api/strategies")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ok"] is True
    assert "threshold" in data["strategies"]


def test_market_options(client):
    resp = client.get("/api/market/options")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ok"] is True


def test_config_no_auth_fails(auth_client):
    resp = auth_client.post("/api/config", json={"symbol": "BTCUSDT"})
    assert resp.status_code == 401


@patch.dict(os.environ, {"API_KEY": "test-key-123"})
def test_config_with_auth_succeeds():
    app.config["TESTING"] = True
    with patch("app.service") as mock_svc:
        mock_svc.snapshot.return_value = {"symbol": "BTCUSDT"}
        with app.test_client() as c:
            resp = c.post("/api/config", json={"symbol": "BTCUSDT"},
                          headers={"X-API-Key": "test-key-123"})
            assert resp.status_code == 200


@patch.dict(os.environ, {"API_KEY": "test-key-123"})
def test_config_with_wrong_auth_fails():
    app.config["TESTING"] = True
    with app.test_client() as c:
        resp = c.post("/api/config", json={"symbol": "BTCUSDT"},
                      headers={"X-API-Key": "wrong-key"})
        assert resp.status_code == 401


def test_auto_start_no_auth(auth_client):
    resp = auth_client.post("/api/auto/start", json={})
    assert resp.status_code in (400, 401)


def test_manual_buy_no_auth(auth_client):
    resp = auth_client.post("/api/manual/buy")
    assert resp.status_code in (400, 401)


def test_manual_sell_no_auth(auth_client):
    resp = auth_client.post("/api/manual/sell")
    assert resp.status_code in (400, 401)


def test_backtest_no_auth(auth_client):
    resp = auth_client.post("/api/backtest", json={})
    assert resp.status_code in (400, 401)


def test_trades(client):
    resp = client.get("/api/trades")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ok"] is True


def test_sessions(client):
    resp = client.get("/api/sessions")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ok"] is True


def test_stream_is_sse(client):
    resp = client.get("/api/stream")
    assert resp.status_code == 200
    assert resp.mimetype == "text/event-stream"


def test_logs_clear_no_auth(auth_client):
    resp = auth_client.post("/api/logs/clear")
    assert resp.status_code == 401


def test_health_rate_limit_exempt(client):
    for _ in range(10):
        resp = client.get("/api/health")
        assert resp.status_code == 200
