import json
import sqlite3
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path


class Database:
    def __init__(self, db_path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _conn(self):
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _init_db(self):
        with self._conn() as c:
            c.executescript("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    label TEXT,
                    symbol TEXT,
                    start_time TEXT NOT NULL,
                    end_time TEXT,
                    initial_balance REAL DEFAULT 0,
                    final_balance REAL DEFAULT 0,
                    pnl REAL DEFAULT 0,
                    trades_count INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'active'
                );

                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    price REAL,
                    quantity REAL,
                    quote_qty REAL,
                    pnl REAL,
                    fee REAL DEFAULT 0,
                    timestamp TEXT NOT NULL,
                    reason TEXT,
                    simulated INTEGER DEFAULT 1,
                    FOREIGN KEY (session_id) REFERENCES sessions(id)
                );

                CREATE TABLE IF NOT EXISTS config (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
            """)

    def save_config(self, key, value):
        with self._conn() as c:
            c.execute(
                "INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)",
                (key, json.dumps(value)),
            )

    def get_config(self, key, default=None):
        with self._conn() as c:
            row = c.execute("SELECT value FROM config WHERE key = ?", (key,)).fetchone()
            if row:
                return json.loads(row["value"])
            return default

    def get_all_config(self):
        with self._conn() as c:
            rows = c.execute("SELECT key, value FROM config").fetchall()
            return {row["key"]: json.loads(row["value"]) for row in rows}

    def save_state(self, state):
        def to_float(v):
            if v is None: return None
            try: return float(v)
            except: return None
        sp = state.get("strategy_params")
        if sp:
            sp = {k: float(v) if isinstance(v, Decimal) else v for k, v in sp.items()}
        fields = {
            "symbol": state.get("symbol"),
            "quote_amount": to_float(state.get("quote_amount")),
            "buy_price": to_float(state.get("buy_price")),
            "sell_price": to_float(state.get("sell_price")),
            "stop_loss_enabled": state.get("stop_loss_enabled", False),
            "stop_loss_price": to_float(state.get("stop_loss_price")),
            "chart_interval": state.get("chart_interval", "15m"),
            "session_pnl": to_float(state.get("session_pnl")) or 0,
            "operations_count": state.get("operations_count", 0),
            "strategy": state.get("strategy"),
            "strategy_params": sp,
            "trailing_stop_active": state.get("trailing_stop_active", False),
            "trailing_stop_pct": to_float(state.get("trailing_stop_pct")),
            "tp_active": state.get("tp_active", False),
            "tp_levels": state.get("tp_levels", "3,5,10"),
            "tp_allocations": state.get("tp_allocations", "33,33,34"),
            "dca_active": state.get("dca_active", False),
            "dca_amount": to_float(state.get("dca_amount")),
            "dca_interval_minutes": state.get("dca_interval_minutes", 60),
            "last_dca_time": state.get("last_dca_time"),
        }
        for key, val in fields.items():
            self.save_config(f"state.{key}", val)

    def restore_state(self):
        config = self.get_all_config()
        state = {}
        prefix = "state."
        for key, val in config.items():
            if key.startswith(prefix):
                field = key[len(prefix):]
                state[field] = val
        return state

    def create_session(self, symbol, initial_balance=0):
        now = datetime.now(timezone.utc).isoformat()
        with self._conn() as c:
            cur = c.execute(
                "INSERT INTO sessions (symbol, start_time, initial_balance, status) VALUES (?, ?, ?, 'active')",
                (symbol, now, initial_balance),
            )
            return cur.lastrowid

    def close_active_session(self):
        with self._conn() as c:
            row = c.execute(
                "SELECT id, pnl FROM sessions WHERE status = 'active' ORDER BY start_time DESC LIMIT 1"
            ).fetchone()
            if row:
                now = datetime.now(timezone.utc).isoformat()
                c.execute(
                    "UPDATE sessions SET end_time = ?, status = 'closed' WHERE id = ?",
                    (now, row["id"]),
                )

    def add_trade(self, session_id, symbol, side, price, quantity, quote_qty,
                  pnl=None, fee=0, reason="manual", simulated=True):
        now = datetime.now(timezone.utc).isoformat()
        with self._conn() as c:
            c.execute(
                """INSERT INTO trades
                   (session_id, symbol, side, price, quantity, quote_qty,
                    pnl, fee, timestamp, reason, simulated)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (session_id, symbol, side,
                 float(price) if price else None,
                 float(quantity) if quantity else None,
                 float(quote_qty) if quote_qty else None,
                 float(pnl) if pnl else None,
                 float(fee), now, reason, 1 if simulated else 0),
            )
            c.execute(
                "UPDATE sessions SET trades_count = trades_count + 1, pnl = COALESCE(pnl, 0) + COALESCE(?, 0) WHERE id = ?",
                (float(pnl) if pnl else 0, session_id),
            )

    def get_trades(self, session_id=None, limit=100):
        with self._conn() as c:
            if session_id:
                rows = c.execute(
                    "SELECT * FROM trades WHERE session_id = ? ORDER BY timestamp DESC LIMIT ?",
                    (session_id, limit),
                ).fetchall()
            else:
                rows = c.execute(
                    "SELECT * FROM trades ORDER BY timestamp DESC LIMIT ?", (limit,)
                ).fetchall()
            return [dict(r) for r in rows]

    def get_sessions(self, limit=20):
        with self._conn() as c:
            rows = c.execute(
                "SELECT * FROM sessions ORDER BY start_time DESC LIMIT ?", (limit,)
            ).fetchall()
            return [dict(r) for r in rows]

    def get_active_session(self):
        with self._conn() as c:
            row = c.execute(
                "SELECT * FROM sessions WHERE status = 'active' ORDER BY start_time DESC LIMIT 1"
            ).fetchone()
            return dict(row) if row else None

    def close(self):
        pass  # connections are short-lived via 'with self._conn()'

    def run_backtest(self, symbol, interval, klines, quote_amount,
                     evaluate_fn):
        results = {
            "symbol": symbol,
            "interval": interval,
            "total_trades": 0,
            "winning": 0,
            "losing": 0,
            "total_pnl": 0.0,
            "max_drawdown": 0.0,
            "win_rate": 0.0,
            "return_pct": 0.0,
            "final_equity": float(quote_amount),
            "trades": [],
        }

        position_open = False
        position_qty = 0.0
        position_entry = 0.0
        position_spent = 0.0
        peak = float(quote_amount)
        equity = float(quote_amount)

        def close_trade(price, reason):
            nonlocal position_open, position_qty, position_entry, position_spent, equity, peak
            received = position_qty * price
            pnl = received - position_spent
            equity += pnl
            results["total_pnl"] += pnl
            results["total_trades"] += 1
            if pnl > 0:
                results["winning"] += 1
            else:
                results["losing"] += 1
            results["trades"].append({
                "time": None,
                "side": "SELL",
                "price": round(price, 8),
                "quantity": round(position_qty, 8),
                "quote_qty": round(received, 2),
                "pnl": round(pnl, 2),
                "reason": reason,
            })
            position_open = False
            position_qty = 0.0
            if equity > peak:
                peak = equity
            dd = (peak - equity) / peak if peak > 0 else 0
            if dd > results["max_drawdown"]:
                results["max_drawdown"] = dd

        closes = [c["close"] for c in klines]
        highs = [c["high"] for c in klines]
        lows = [c["low"] for c in klines]

        for i in range(len(klines)):
            closes_up_to = closes[: i + 1]
            highs_up_to = highs[: i + 1]
            lows_up_to = lows[: i + 1]
            candle = klines[i]

            if not position_open:
                signal = evaluate_fn(closes_up_to, highs_up_to, lows_up_to, False)
                if signal and signal.get("action") == "buy":
                    price = closes_up_to[-1]
                    position_qty = float(quote_amount) / price
                    position_entry = price
                    position_spent = float(quote_amount)
                    position_open = True
                    results["trades"].append({
                        "time": candle["open_time"],
                        "side": "BUY",
                        "price": round(price, 8),
                        "quantity": round(position_qty, 8),
                        "quote_qty": float(quote_amount),
                    })
            else:
                signal = evaluate_fn(closes_up_to, highs_up_to, lows_up_to, True)
                if signal and signal.get("action") == "sell":
                    price = closes_up_to[-1]
                    close_trade(price, signal.get("reason", "signal"))
                elif candle["low"] <= position_entry * 0.95:
                    close_trade(position_entry * 0.95, "stop-loss-emergencia")

        if position_open and klines:
            close_trade(klines[-1]["close"], "cierre")

        if results["total_trades"] > 0:
            results["win_rate"] = round((results["winning"] / results["total_trades"]) * 100, 2)
        results["final_equity"] = round(equity, 2)
        results["return_pct"] = round(
            ((equity - quote_amount) / quote_amount) * 100 if quote_amount > 0 else 0, 2
        )
        results["max_drawdown"] = round(results["max_drawdown"] * 100, 2)
        return results
