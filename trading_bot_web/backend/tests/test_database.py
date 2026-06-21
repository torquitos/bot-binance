import tempfile
from pathlib import Path
from bot.database import Database


def _db(tmp):
    return Database(Path(tmp) / "test.db")


def test_init():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        db = _db(tmp)
        assert db.db_path.exists()


def test_config():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        db = _db(tmp)
        db.save_config("foo", "bar")
        assert db.get_config("foo") == "bar"
        assert db.get_config("nonexistent", 42) == 42


def test_save_restore_state():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        db = _db(tmp)
        state = {"symbol": "BTCUSDT", "quote_amount": 100.0, "strategy": "rsi"}
        db.save_state(state)
        restored = db.restore_state()
        assert restored["symbol"] == "BTCUSDT"
        assert restored["quote_amount"] == 100.0
        assert restored["strategy"] == "rsi"


def test_session():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        db = _db(tmp)
        sid = db.create_session("BTCUSDT", 100.0)
        assert sid is not None
        active = db.get_active_session()
        assert active is not None
        assert active["id"] == sid
        db.close_active_session()
        assert db.get_active_session() is None


def test_trade():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        db = _db(tmp)
        sid = db.create_session("BTCUSDT")
        db.add_trade(sid, "BTCUSDT", "BUY", price=50000, quantity=0.002, quote_qty=100)
        assert len(db.get_trades(session_id=sid)) == 1
        db.add_trade(sid, "BTCUSDT", "SELL", price=51000, quantity=0.002, quote_qty=102, pnl=2)
        assert len(db.get_trades(session_id=sid)) == 2
        session = db.get_active_session()
        assert session["trades_count"] == 2


def test_run_backtest():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        db = _db(tmp)
        klines = [
            {"open_time": 1000, "open": 100, "high": 105, "low": 98, "close": 100},
            {"open_time": 2000, "open": 100, "high": 102, "low": 99, "close": 101},
            {"open_time": 3000, "open": 101, "high": 106, "low": 100, "close": 105},
        ]

        def evaluate(closes, highs, lows, pos):
            price = closes[-1]
            if not pos and price <= 100:
                return {"action": "buy", "reason": "test"}
            if pos and price >= 105:
                return {"action": "sell", "reason": "test"}
            return {"action": None}

        result = db.run_backtest("BTCUSDT", "15m", klines, 100, evaluate)
        assert result["total_trades"] > 0
        assert result["final_equity"] > 0
