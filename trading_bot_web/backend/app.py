import json
import os
import secrets
import time
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify, request, Response, send_from_directory
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from bot.service import TradingBotService
from bot.auth import require_api_key


BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = BASE_DIR.parent / "frontend"

load_dotenv(BASE_DIR / ".env")

app = Flask(__name__, static_folder=str(FRONTEND_DIR), static_url_path="")
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", secrets.token_hex(32))

allowed_origins = os.getenv("CORS_ORIGINS", "http://localhost:5000,http://127.0.0.1:5000")
CORS(app, resources={r"/api/*": {"origins": [o.strip() for o in allowed_origins.split(",") if o.strip()]}})

limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["2000 per hour", "100 per minute"],
    storage_uri="memory://",
)

service = TradingBotService()


def ok(payload=None, status=200):
    data = {"ok": True}
    if payload:
        data.update(payload)
    return jsonify(data), status


def fail(message, status=400):
    return jsonify({"ok": False, "error": message}), status


# ── Static frontend ──

@app.get("/")
def index():
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.get("/<path:path>")
def static_files(path):
    return send_from_directory(FRONTEND_DIR, path)


# ── API ──

@app.get("/api/health")
@limiter.exempt
def api_health():
    return ok({"message": "Backend operativo"})


@app.get("/api/state")
@limiter.exempt
def api_state():
    return ok({"state": service.snapshot()})


@app.get("/api/ticker")
def api_ticker():
    symbol = request.args.get("symbol")
    try:
        return ok({"ticker": service.get_ticker(symbol=symbol)})
    except Exception as exc:
        return fail(str(exc))


@app.get("/api/market/options")
@limiter.exempt
def api_market_options():
    try:
        return ok(service.get_market_options())
    except Exception as exc:
        return fail(str(exc))


@app.get("/api/market/klines")
@limiter.exempt
def api_market_klines():
    symbol = request.args.get("symbol")
    interval = request.args.get("interval")
    limit = request.args.get("limit", default=80, type=int)
    try:
        return ok(service.get_klines(symbol=symbol, interval=interval, limit=limit))
    except Exception as exc:
        return fail(str(exc))


@app.post("/api/config")
@require_api_key
def api_config():
    payload = request.get_json(silent=True) or {}
    try:
        service.update_config(payload)
        return ok({"state": service.snapshot()})
    except Exception as exc:
        return fail(str(exc))


@app.post("/api/manual/buy")
@require_api_key
def api_manual_buy():
    try:
        order = service.manual_buy()
        return ok({"message": "Compra ejecutada.", "order": order, "state": service.snapshot()})
    except Exception as exc:
        return fail(str(exc))


@app.post("/api/manual/sell")
@require_api_key
def api_manual_sell():
    try:
        order, pnl, avg_price, qty = service.manual_sell()
        return ok({
            "message": "Venta ejecutada.",
            "order": order,
            "result": {
                "realized_pnl": float(pnl),
                "avg_price": float(avg_price) if avg_price else None,
                "quantity": float(qty),
            },
            "state": service.snapshot(),
        })
    except Exception as exc:
        return fail(str(exc))


@app.post("/api/auto/start")
@require_api_key
def api_auto_start():
    try:
        payload = request.get_json(silent=True) or {}
        if payload:
            service.update_config(payload)
        service.start_auto()
        return ok({"message": "Bot automatico iniciado.", "state": service.snapshot()})
    except Exception as exc:
        return fail(str(exc))


@app.post("/api/auto/stop")
@require_api_key
def api_auto_stop():
    try:
        service.stop_auto()
        return ok({"message": "Bot automatico detenido.", "state": service.snapshot()})
    except Exception as exc:
        return fail(str(exc))


@app.get("/api/logs")
def api_logs_get():
    try:
        return ok({"logs": service.state.get("logs", [])})
    except Exception as exc:
        return fail(str(exc))


@app.post("/api/logs/clear")
@require_api_key
def api_logs_clear():
    try:
        service.clear_logs()
        return ok({"message": "Logs limpiados.", "state": service.snapshot()})
    except Exception as exc:
        return fail(str(exc))


@app.get("/api/trades")
def api_trades():
    limit = request.args.get("limit", default=50, type=int)
    try:
        trades = service.get_trade_history(limit=limit)
        return ok({"trades": trades})
    except Exception as exc:
        return fail(str(exc))


@app.get("/api/strategies")
@limiter.exempt
def api_strategies():
    return ok({"strategies": service.get_strategies()})


@app.get("/api/sessions")
@limiter.exempt
def api_sessions():
    try:
        sessions = service.get_all_sessions()
        return ok({"sessions": sessions})
    except Exception as exc:
        return fail(str(exc))


@app.post("/api/backtest")
@require_api_key
def api_backtest():
    payload = request.get_json(silent=True) or {}
    s = service.state or {}
    symbol = payload.get("symbol", s.get("symbol", "BTCUSDT"))
    interval = payload.get("interval", s.get("chart_interval", "15m"))
    strategy_name = payload.get("strategy", "threshold")
    strategy_params = payload.get("strategy_params", {})
    quote_amount = payload.get("quote_amount", 100)
    kline_limit = payload.get("kline_limit", 500)

    if strategy_name == "threshold":
        if "buy_price" not in strategy_params and payload.get("buy_price"):
            strategy_params["buy_price"] = float(payload["buy_price"])
        if "sell_price" not in strategy_params and payload.get("sell_price"):
            strategy_params["sell_price"] = float(payload["sell_price"])
        if "stop_loss_price" not in strategy_params and payload.get("stop_loss"):
            strategy_params["stop_loss_price"] = float(payload["stop_loss"])

    compound = payload.get("compound", False)

    try:
        result = service.run_backtest(
            symbol=symbol,
            interval=interval,
            strategy_name=strategy_name,
            strategy_params=strategy_params,
            quote_amount=float(quote_amount),
            kline_limit=int(kline_limit),
            emergency_stop_pct=float(payload.get("emergency_stop_pct", 5)),
            compound=bool(compound),
        )
        return ok({"backtest": result})
    except Exception as exc:
        return fail(str(exc))


@app.post("/api/session/new")
@require_api_key
def api_session_new():
    try:
        service.new_session()
        return ok({"message": "Nueva sesion creada.", "state": service.snapshot()})
    except Exception as exc:
        return fail(str(exc))


@app.post("/api/credentials")
def api_credentials():
    payload = request.get_json(silent=True) or {}
    api_key = (payload.get("api_key") or "").strip()
    api_secret = (payload.get("api_secret") or "").strip()
    use_testnet = payload.get("use_testnet", True)
    try:
        service.update_credentials(api_key=api_key, api_secret=api_secret, use_testnet=use_testnet)
        return ok({"message": "Credenciales actualizadas", "state": service.snapshot()})
    except Exception as exc:
        return fail(str(exc))


@app.get("/api/stream")
@limiter.exempt
def api_stream():
    def generate():
        while True:
            try:
                data = service.snapshot()
                yield f"data: {json.dumps(data)}\n\n"
            except Exception:
                yield f"data: {json.dumps({'error': 'stream error'})}\n\n"
            time.sleep(1)
    return Response(generate(), mimetype="text/event-stream", headers={
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    })


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    debug = os.getenv("FLASK_ENV", "production") == "development"
    app.run(debug=debug, host="0.0.0.0", port=port)
