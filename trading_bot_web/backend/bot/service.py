import json
import os
import threading
import time
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_DOWN
from pathlib import Path

from binance.client import Client

from bot.database import Database
from bot.strategies import STRATEGY_DEFS, evaluate as eval_strategy
from bot.indicators import compute_all
from bot.notifier import Notifier
from bot.ws_manager import WSManager


class TradingBotService:
    INTERVAL_OPTIONS = ["1m", "5m", "15m", "30m", "1h", "4h", "1d"]

    def __init__(self):
        self.data_dir = Path(__file__).resolve().parent.parent / "data"
        self.data_dir.mkdir(exist_ok=True)
        self.log_file = self.data_dir / "activity.log"

        self.db = Database(self.data_dir / "bot.db")

        self.lock = threading.RLock()
        self.auto_thread = None
        self.stop_event = threading.Event()

        self.api_key = os.getenv("BINANCE_API_KEY", "").strip()
        self.api_secret = os.getenv("BINANCE_API_SECRET", "").strip()
        self.use_testnet = os.getenv("BINANCE_USE_TESTNET", "true").lower() == "true"
        self.real_orders_enabled = os.getenv("BINANCE_ENABLE_REAL_ORDERS", "false").lower() == "true"

        self.client = None
        self.exchange_filters = {}
        self.exchange_symbols_cache = []
        self.last_error = None
        self._build_client()

        saved = self.db.restore_state()

        default_strategy = "threshold"
        saved_strategy = saved.get("strategy", default_strategy)
        if saved_strategy not in STRATEGY_DEFS:
            saved_strategy = default_strategy

        saved_params = saved.get("strategy_params", {})
        def_params = {
            k: v["default"] for k, v in STRATEGY_DEFS.get(saved_strategy, {}).get("params", {}).items()
        }
        def_params.update(saved_params)

        self.state = {
            "symbol": str(saved.get("symbol", os.getenv("DEFAULT_SYMBOL", "BTCUSDT"))).upper(),
            "quote_amount": self._to_decimal(saved.get("quote_amount", os.getenv("DEFAULT_QUOTE_AMOUNT", "100"))),
            "buy_price": self._to_decimal(saved.get("buy_price")),
            "sell_price": self._to_decimal(saved.get("sell_price")),
            "stop_loss_enabled": bool(saved.get("stop_loss_enabled", False)),
            "stop_loss_price": self._to_decimal(saved.get("stop_loss_price")),
            "strategy": saved_strategy,
            "strategy_params": def_params,
            "mode": "manual",
            "bot_active": False,
            "last_price": None,
            "session_pnl": self._to_decimal(saved.get("session_pnl", 0)),
            "operations_count": int(saved.get("operations_count", 0)),
            "position_open": False,
            "position_qty": Decimal("0"),
            "position_entry_price": None,
            "position_quote_spent": Decimal("0"),
            "last_order_side": None,
            "status": "Listo para configurar",
            "chart_interval": str(saved.get("chart_interval", "15m")),
            "logs": [],
            # Trailing stop
            "trailing_stop_active": bool(saved.get("trailing_stop_active", False)),
            "trailing_stop_pct": self._to_decimal(saved.get("trailing_stop_pct", 2.0)),
            "position_highest_price": None,
            # Partial take-profit
            "tp_active": bool(saved.get("tp_active", False)),
            "tp_levels": str(saved.get("tp_levels", "3,5,10")),
            "tp_allocations": str(saved.get("tp_allocations", "33,33,34")),
            "tp_hit_indices": [],
            "position_initial_qty": Decimal("0"),
            # DCA
            "dca_active": bool(saved.get("dca_active", False)),
            "dca_amount": self._to_decimal(saved.get("dca_amount", 100)),
            "dca_interval_minutes": int(saved.get("dca_interval_minutes", 60)),
            "last_dca_time": saved.get("last_dca_time"),
        }

        self.session_id = None
        self._ensure_session()

        self.notifier = Notifier()
        self.ws = WSManager(api_key=self.api_key, api_secret=self.api_secret, testnet=self.use_testnet)
        self._ws_started = False

        self.log("info", f"Backend iniciado. Estrategia: {STRATEGY_DEFS.get(self.state['strategy'], {}).get('label', self.state['strategy'])}")

    def _ensure_session(self):
        active = self.db.get_active_session()
        if active:
            self.session_id = active["id"]
        else:
            self.session_id = self.db.create_session(self.state["symbol"])

    def _init_ws(self):
        if not self.api_key or not self.api_secret:
            return
        try:
            # Always create fresh WSManager to avoid "threads can only be started once"
            self.ws = WSManager(api_key=self.api_key, api_secret=self.api_secret, testnet=self.use_testnet)
            self.ws.start()
            self._ws_started = True
            self._ws_subscribe_ticker()
        except Exception as e:
            self.log("error", f"No se pudo iniciar WebSocket: {e}")

    def _ws_subscribe_ticker(self):
        if not self.ws or not self._ws_started:
            return
        symbol = self.state["symbol"]

        def on_ticker(msg):
            if msg.get("e") == "24hrTicker":
                price_str = msg.get("c")
                if price_str:
                    price = self._to_decimal(price_str)
                    if price:
                        with self.lock:
                            self.state["last_price"] = price

        self.ws.update_symbol(symbol, on_ticker)

    def _build_client(self):
        if not self.api_key or not self.api_secret:
            self.last_error = "Faltan BINANCE_API_KEY y BINANCE_API_SECRET en backend/.env."
            return
        try:
            self.client = Client(self.api_key, self.api_secret)
            if self.use_testnet:
                self.client.API_URL = "https://testnet.binance.vision/api"
            self.client.get_account()
            self.last_error = None
            self._init_ws()
        except Exception as e:
            self.last_error = f"Error conectando a Binance: {e}"
            self.client = None

    def _ensure_client(self):
        if self.client:
            try:
                self.client.get_account()
                return True
            except Exception:
                pass
        self._build_client()
        return self.client is not None

    def _to_decimal(self, value, default=None):
        try:
            return Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError):
            return default

    def _decimal_to_float(self, value):
        if value is None:
            return None
        return float(value)

    def _decimal_to_str(self, value):
        if value is None:
            return None
        normalized = value.normalize()
        return format(normalized, "f")

    def _now(self):
        return datetime.now(timezone.utc).strftime("%H:%M:%S")

    def log(self, level, message):
        entry = {"time": self._now(), "level": level, "message": message}
        with self.lock:
            self.state["logs"] = [entry] + self.state["logs"][:149]
        with self.log_file.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=True) + "\n")

    def clear_logs(self):
        with self.lock:
            self.state["logs"] = []
        self.log_file.write_text("", encoding="utf-8")
        self.log("info", "Registro limpiado.")

    def is_ready(self):
        return self.client is not None

    def get_strategies(self):
        return STRATEGY_DEFS

    def ensure_symbol_info(self, symbol):
        if symbol in self.exchange_filters:
            return self.exchange_filters[symbol]
        if not self._ensure_client():
            raise RuntimeError(self.last_error or "Sin conexion a Binance.")
        info = self.client.get_symbol_info(symbol)
        if not info:
            raise ValueError(f"El simbolo {symbol} no existe en Binance Spot.")

        symbol_info = {
            "baseAsset": info["baseAsset"],
            "quoteAsset": info["quoteAsset"],
            "stepSize": Decimal("0.000001"),
            "minQty": Decimal("0"),
            "minNotional": Decimal("0"),
        }
        for item in info.get("filters", []):
            if item["filterType"] == "LOT_SIZE":
                symbol_info["stepSize"] = Decimal(item["stepSize"])
                symbol_info["minQty"] = Decimal(item["minQty"])
            if item["filterType"] == "NOTIONAL":
                symbol_info["minNotional"] = Decimal(item["minNotional"])
            if item["filterType"] == "MIN_NOTIONAL":
                symbol_info["minNotional"] = Decimal(item["minNotional"])

        self.exchange_filters[symbol] = symbol_info
        return symbol_info

    def get_available_symbols(self, limit=40):
        if not self.is_ready():
            return ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT"]
        if self.exchange_symbols_cache:
            return self.exchange_symbols_cache[:limit]
        if not self._ensure_client():
            return ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT"]
        exchange_info = self.client.get_exchange_info()
        symbols = []
        for item in exchange_info.get("symbols", []):
            if item.get("status") != "TRADING":
                continue
            if item.get("quoteAsset") != "USDT":
                continue
            if item.get("isSpotTradingAllowed") is False:
                continue
            symbols.append(item["symbol"])
        preferred = [
            "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT",
            "ADAUSDT", "DOGEUSDT", "AVAXUSDT", "LINKUSDT", "TRXUSDT",
        ]
        remaining = sorted([s for s in symbols if s not in preferred])
        ordered = [s for s in preferred if s in symbols] + remaining
        self.exchange_symbols_cache = ordered
        return ordered[:limit]

    def get_market_options(self):
        return {
            "symbols": self.get_available_symbols(),
            "intervals": self.INTERVAL_OPTIONS,
        }

    def get_klines(self, symbol=None, interval=None, limit=80):
        if not self._ensure_client():
            raise RuntimeError(self.last_error or "Configura tus llaves de Binance.")
        symbol = (symbol or self.state["symbol"]).upper().replace("/", "")
        interval = interval or self.state["chart_interval"]
        if interval not in self.INTERVAL_OPTIONS:
            raise ValueError(f"Intervalo no soportado: {interval}")
        raw_klines = self.client.get_klines(symbol=symbol, interval=interval, limit=limit)
        candles = []
        for item in raw_klines:
            candles.append({
                "open_time": item[0],
                "open": float(item[1]),
                "high": float(item[2]),
                "low": float(item[3]),
                "close": float(item[4]),
                "volume": float(item[5]),
                "close_time": item[6],
            })
        return {"symbol": symbol, "interval": interval, "candles": candles}

    def get_klines_raw(self, symbol, interval, limit=500):
        if not self._ensure_client():
            raise RuntimeError(self.last_error or "Sin conexion a Binance.")
        raw = self.client.get_klines(symbol=symbol, interval=interval, limit=limit)
        candles = []
        for item in raw:
            candles.append({
                "open_time": item[0],
                "open": float(item[1]),
                "high": float(item[2]),
                "low": float(item[3]),
                "close": float(item[4]),
                "volume": float(item[5]),
            })
        return candles

    def get_indicators(self, symbol=None, interval=None, limit=250):
        if not self._ensure_client():
            return None
        symbol = symbol or self.state["symbol"]
        interval = interval or self.state["chart_interval"]
        klines = self.get_klines_raw(symbol, interval, limit=limit)
        if not klines:
            return None
        closes = [c["close"] for c in klines]
        return compute_all(closes)

    def quantize_quantity(self, qty, step):
        if step <= 0:
            return qty
        return qty.quantize(step, rounding=ROUND_DOWN)

    def get_live_price(self, symbol=None):
        symbol = symbol or self.state["symbol"]
        if not self._ensure_client():
            return None
        try:
            ticker = self.client.get_symbol_ticker(symbol=symbol)
            price = self._to_decimal(ticker["price"])
            with self.lock:
                self.state["last_price"] = price
            return price
        except Exception:
            self._build_client()
            return None

    def get_ticker(self, symbol=None):
        symbol = (symbol or self.state["symbol"]).upper().replace("/", "")
        if not self._ensure_client():
            raise RuntimeError(self.last_error or "Configura tus llaves de Binance.")
        price = self.get_live_price(symbol)
        info = self.ensure_symbol_info(symbol)
        return {
            "symbol": symbol,
            "base_asset": info["baseAsset"],
            "quote_asset": info["quoteAsset"],
            "price": self._decimal_to_float(price),
        }

    def get_balances(self):
        if not self._ensure_client():
            return {}
        try:
            account = self.client.get_account()
            balances = {}
            for item in account.get("balances", []):
                free = self._to_decimal(item["free"], Decimal("0"))
                locked = self._to_decimal(item["locked"], Decimal("0"))
                total = free + locked
                if total > 0:
                    balances[item["asset"]] = {
                        "free": free,
                        "locked": locked,
                        "total": total,
                    }
            return balances
        except Exception:
            self._build_client()
            return {}

    def update_credentials(self, api_key, api_secret, use_testnet=True):
        with self.lock:
            self.api_key = api_key
            self.api_secret = api_secret
            self.use_testnet = bool(use_testnet)
            if self._ws_started:
                self.ws.stop()
                self._ws_started = False
            self.client = None
            self._build_client()
            self.state["use_testnet"] = self.use_testnet
            self.state["credentials_ready"] = bool(api_key and api_secret)
            self.log("info", "Credenciales actualizadas" + (" (Testnet)" if self.use_testnet else ""))

    def update_config(self, payload):
        with self.lock:
            symbol = str(payload.get("symbol", self.state["symbol"])).upper().replace("/", "")
            quote_amount = self._to_decimal(payload.get("quote_amount"), self.state["quote_amount"])
            buy_price = self._to_decimal(payload.get("buy_price"))
            sell_price = self._to_decimal(payload.get("sell_price"))
            stop_loss_enabled = bool(payload.get("stop_loss_enabled"))
            stop_loss_price = self._to_decimal(payload.get("stop_loss_price"))
            chart_interval = str(payload.get("chart_interval", self.state["chart_interval"]))
            strategy = str(payload.get("strategy", self.state.get("strategy", "threshold")))

            self.state["symbol"] = symbol
            self.state["quote_amount"] = quote_amount
            self.state["buy_price"] = buy_price
            self.state["sell_price"] = sell_price
            self.state["stop_loss_enabled"] = stop_loss_enabled
            self.state["stop_loss_price"] = stop_loss_price if stop_loss_enabled else None
            self.state["chart_interval"] = chart_interval if chart_interval in self.INTERVAL_OPTIONS else self.state["chart_interval"]

            self.state["trailing_stop_active"] = bool(payload.get("trailing_stop_active", self.state["trailing_stop_active"]))
            self.state["trailing_stop_pct"] = self._to_decimal(payload.get("trailing_stop_pct"), self.state["trailing_stop_pct"])
            self.state["tp_active"] = bool(payload.get("tp_active", self.state["tp_active"]))
            if "tp_levels" in payload:
                self.state["tp_levels"] = str(payload["tp_levels"])
            if "tp_allocations" in payload:
                self.state["tp_allocations"] = str(payload["tp_allocations"])
            self.state["dca_active"] = bool(payload.get("dca_active", self.state["dca_active"]))
            self.state["dca_amount"] = self._to_decimal(payload.get("dca_amount"), self.state["dca_amount"])
            dca_int = payload.get("dca_interval_minutes")
            if dca_int is not None:
                self.state["dca_interval_minutes"] = int(dca_int)

            if strategy in STRATEGY_DEFS:
                self.state["strategy"] = strategy
                new_params = dict(payload.get("strategy_params", {}))
                defs = STRATEGY_DEFS[strategy]["params"]
                for k, v in defs.items():
                    if k not in new_params or new_params[k] is None:
                        new_params[k] = self.state.get("strategy_params", {}).get(k, v.get("default"))
                self.state["strategy_params"] = new_params

        self.db.save_state(self.state)
        strat_label = STRATEGY_DEFS.get(self.state["strategy"], {}).get("label", self.state["strategy"])
        self.log("info", f"Config actualizada. Estrategia: {strat_label}")
        self._ws_subscribe_ticker()

    def _parse_order_fill(self, order):
        fills = order.get("fills", [])
        executed_qty = self._to_decimal(order.get("executedQty"), Decimal("0"))
        cummulative_quote_qty = self._to_decimal(order.get("cummulativeQuoteQty"), Decimal("0"))
        avg_price = None
        if executed_qty and cummulative_quote_qty:
            avg_price = cummulative_quote_qty / executed_qty
        elif fills:
            total_qty = Decimal("0")
            total_quote = Decimal("0")
            for fill in fills:
                fill_qty = self._to_decimal(fill["qty"], Decimal("0"))
                fill_price = self._to_decimal(fill["price"], Decimal("0"))
                total_qty += fill_qty
                total_quote += fill_qty * fill_price
            if total_qty:
                avg_price = total_quote / total_qty
                executed_qty = total_qty
                cummulative_quote_qty = total_quote
        return executed_qty, cummulative_quote_qty, avg_price

    def _simulate_buy(self):
        price = self.get_live_price()
        if not price:
            raise RuntimeError("No pude obtener el precio en vivo.")
        quote_amount = self.state["quote_amount"]
        qty = quote_amount / price
        return {
            "symbol": self.state["symbol"],
            "status": "FILLED",
            "side": "BUY",
            "type": "MARKET",
            "executedQty": self._decimal_to_str(qty),
            "cummulativeQuoteQty": self._decimal_to_str(quote_amount),
            "orderId": "SIMULATED-BUY",
            "transactTime": int(time.time() * 1000),
        }

    def _simulate_sell(self):
        price = self.get_live_price()
        if not price:
            raise RuntimeError("No pude obtener el precio en vivo.")
        qty = self.state["position_qty"]
        quote_qty = qty * price
        return {
            "symbol": self.state["symbol"],
            "status": "FILLED",
            "side": "SELL",
            "type": "MARKET",
            "executedQty": self._decimal_to_str(qty),
            "cummulativeQuoteQty": self._decimal_to_str(quote_qty),
            "orderId": "SIMULATED-SELL",
            "transactTime": int(time.time() * 1000),
        }

    def manual_buy(self):
        if not self._ensure_client():
            raise RuntimeError(self.last_error or "Configura tus llaves de Binance.")
        with self.lock:
            if self.state["position_open"]:
                raise RuntimeError("Ya hay una posicion abierta.")
            symbol = self.state["symbol"]
            quote_amount = self.state["quote_amount"]
        symbol_info = self.ensure_symbol_info(symbol)
        if quote_amount <= 0:
            raise RuntimeError("El monto debe ser mayor que 0.")
        if quote_amount < symbol_info["minNotional"]:
            raise RuntimeError(f"Minimo {symbol_info['minNotional']} {symbol_info['quoteAsset']}.")
        if self.real_orders_enabled:
            order = self.client.order_market_buy(symbol=symbol, quoteOrderQty=self._decimal_to_str(quote_amount))
        else:
            order = self._simulate_buy()
        executed_qty, spent, avg_price = self._parse_order_fill(order)
        with self.lock:
            self.state["position_open"] = True
            self.state["position_qty"] = executed_qty
            self.state["position_quote_spent"] = spent
            self.state["position_entry_price"] = avg_price
            self.state["position_initial_qty"] = executed_qty
            self.state["position_highest_price"] = avg_price
            self.state["tp_hit_indices"] = []
            self.state["operations_count"] += 1
            self.state["last_order_side"] = "BUY"
            self.state["status"] = "Posicion abierta"
        self.db.add_trade(
            session_id=self.session_id, symbol=symbol, side="BUY",
            price=float(avg_price) if avg_price else None,
            quantity=float(executed_qty), quote_qty=float(spent),
            reason="manual", simulated=not self.real_orders_enabled,
        )
        self.db.save_state(self.state)
        mode_note = "REAL" if self.real_orders_enabled else "SIMULACION"
        self.log("buy", f"Compra ({mode_note}) por {spent} USDT en {symbol}.")
        self.notifier.buy(symbol, float(spent), float(avg_price) if avg_price else 0, mode_note)
        return order

    def manual_sell(self, reason="manual"):
        if not self._ensure_client():
            raise RuntimeError(self.last_error or "Configura tus llaves de Binance.")
        with self.lock:
            if not self.state["position_open"]:
                raise RuntimeError("No hay posicion abierta.")
            symbol = self.state["symbol"]
            qty = self.state["position_qty"]
            quote_spent = self.state["position_quote_spent"]
        symbol_info = self.ensure_symbol_info(symbol)
        if qty <= 0:
            raise RuntimeError("Cantidad invalida.")
        if self.real_orders_enabled:
            quantity = self.quantize_quantity(qty, symbol_info["stepSize"])
            order = self.client.order_market_sell(symbol=symbol, quantity=self._decimal_to_str(quantity))
        else:
            order = self._simulate_sell()
        executed_qty, quote_received, avg_price = self._parse_order_fill(order)
        realized_pnl = quote_received - quote_spent
        with self.lock:
            self.state["position_open"] = False
            self.state["position_qty"] = Decimal("0")
            self.state["position_quote_spent"] = Decimal("0")
            self.state["position_entry_price"] = None
            self.state["session_pnl"] += realized_pnl
            self.state["operations_count"] += 1
            self.state["last_order_side"] = "SELL"
            self.state["status"] = "Posicion cerrada"
        self.db.add_trade(
            session_id=self.session_id, symbol=symbol, side="SELL",
            price=float(avg_price) if avg_price else None,
            quantity=float(executed_qty), quote_qty=float(quote_received),
            pnl=float(realized_pnl), reason=reason,
            simulated=not self.real_orders_enabled,
        )
        self.db.save_state(self.state)
        mode_note = "REAL" if self.real_orders_enabled else "SIMULACION"
        self.log("sell", f"Venta ({mode_note}) motivo {reason}. PnL: {realized_pnl} USDT.")
        self.notifier.sell(symbol, float(realized_pnl), reason, mode_note)
        return order, realized_pnl, avg_price, executed_qty

    def _sell_partial(self, qty, reason="partial"):
        if not self._ensure_client():
            raise RuntimeError(self.last_error or "Configura tus llaves de Binance.")
        with self.lock:
            if not self.state["position_open"]:
                raise RuntimeError("No hay posicion abierta.")
            if qty <= 0 or qty > self.state["position_qty"]:
                raise RuntimeError("Cantidad invalida para venta parcial.")
            symbol = self.state["symbol"]
            total_qty = self.state["position_qty"]
            total_spent = self.state["position_quote_spent"]
        price = self.get_live_price()
        if not price:
            raise RuntimeError("No pude obtener el precio en vivo.")
        proportional_cost = (qty / total_qty) * total_spent if total_qty else Decimal("0")
        symbol_info = self.ensure_symbol_info(symbol)
        if self.real_orders_enabled:
            quantity = self.quantize_quantity(qty, symbol_info["stepSize"])
            order = self.client.order_market_sell(symbol=symbol, quantity=self._decimal_to_str(quantity))
        else:
            qty_str = self._decimal_to_str(qty)
            quote_received = qty * price
            order = {
                "symbol": symbol, "status": "FILLED", "side": "SELL",
                "type": "MARKET",
                "executedQty": qty_str,
                "cummulativeQuoteQty": self._decimal_to_str(quote_received),
                "orderId": "SIMULATED-SELL-PARTIAL",
                "transactTime": int(time.time() * 1000),
            }
        executed_qty, quote_received, avg_price = self._parse_order_fill(order)
        realized_pnl = quote_received - proportional_cost
        with self.lock:
            self.state["position_qty"] = total_qty - qty
            self.state["position_quote_spent"] = total_spent - proportional_cost
            self.state["session_pnl"] += realized_pnl
            self.state["operations_count"] += 1
            self.state["last_order_side"] = "SELL"
            if self.state["position_qty"] <= 0:
                self.state["position_open"] = False
                self.state["position_entry_price"] = None
                self.state["position_quote_spent"] = Decimal("0")
                self.state["status"] = "Posicion cerrada"
            else:
                self.state["status"] = f"Venta parcial: restan {self.state['position_qty']}"
        self.db.add_trade(
            session_id=self.session_id, symbol=symbol, side="SELL",
            price=float(avg_price) if avg_price else None,
            quantity=float(executed_qty), quote_qty=float(quote_received),
            pnl=float(realized_pnl), reason=reason,
            simulated=not self.real_orders_enabled,
        )
        self.db.save_state(self.state)
        mode_note = "REAL" if self.real_orders_enabled else "SIMULACION"
        self.log("sell", f"Venta parcial ({mode_note}) {reason}. PnL: {realized_pnl} USDT.")
        return order, realized_pnl, avg_price, executed_qty

    def start_auto(self):
        with self.lock:
            if self.state["bot_active"]:
                raise RuntimeError("El bot automatico ya esta en ejecucion.")
            if self.state["strategy"] == "threshold":
                if self.state["buy_price"] is None or self.state["sell_price"] is None:
                    raise RuntimeError("Estrategia umbral: configura precio de compra y venta.")
            self.state["bot_active"] = True
            self.state["mode"] = "automatic"
            self.state["status"] = f"Bot automatico - {STRATEGY_DEFS.get(self.state['strategy'], {}).get('label', self.state['strategy'])}"
        self.stop_event.clear()
        self.auto_thread = threading.Thread(target=self._auto_loop, daemon=True)
        self.auto_thread.start()
        strat_label = STRATEGY_DEFS.get(self.state["strategy"], {}).get("label", self.state["strategy"])
        self.log("info", f"Bot automatico iniciado. Estrategia: {strat_label}")
        self.notifier.start(strat_label, self.state["symbol"])

    def stop_auto(self):
        self.stop_event.set()
        with self.lock:
            self.state["bot_active"] = False
            self.state["mode"] = "manual"
            self.state["status"] = "Bot automatico detenido"
        self.log("info", "Bot automatico detenido.")
        self.notifier.stop()

    def _auto_loop(self):
        while not self.stop_event.is_set():
            try:
                self.step_auto()
            except Exception as exc:
                with self.lock:
                    self.state["status"] = f"Error: {exc}"
                self.log("error", f"Error en loop: {exc}")
            time.sleep(3)

    def step_auto(self):
        self._check_dca()
        strategy = self.state["strategy"]
        if strategy == "threshold":
            self._step_threshold()
        else:
            self._step_indicator_strategy()

    def _check_trailing_stop(self, price):
        if not self.state.get("trailing_stop_active"):
            return False
        with self.lock:
            highest = self.state.get("position_highest_price")
            if highest is None or price > highest:
                self.state["position_highest_price"] = price
                return False
            trail_pct = self.state.get("trailing_stop_pct")
        if trail_pct and trail_pct > 0:
            stop_price = highest * (Decimal("1") - trail_pct / Decimal("100"))
            if price <= stop_price:
                self.log("signal", f"Trailing stop: {price} <= {stop_price:.2f}")
                self.manual_sell("trailing-stop")
                return True
        return False

    def _check_take_profit(self, price):
        if not self.state.get("tp_active") or not self.state.get("position_open"):
            return False
        with self.lock:
            entry = self.state.get("position_entry_price")
            if entry is None or entry <= 0:
                return False
            gain_pct = (price - entry) / entry * Decimal("100")
            levels_str = self.state.get("tp_levels", "")
            allocs_str = self.state.get("tp_allocations", "")
            hit = list(self.state.get("tp_hit_indices", []))
            init_qty = self.state.get("position_initial_qty", self.state["position_qty"])
            cur_qty = self.state["position_qty"]
        if not levels_str or not allocs_str:
            return False
        levels = [Decimal(x.strip()) for x in levels_str.split(",") if x.strip()]
        allocs = [Decimal(x.strip()) for x in allocs_str.split(",") if x.strip()]
        if not levels or not allocs:
            return False
        for i, (level, alloc) in enumerate(zip(levels, allocs)):
            if i in hit:
                continue
            if gain_pct >= level:
                sell_qty = init_qty * alloc / Decimal("100")
                if sell_qty > cur_qty:
                    sell_qty = cur_qty
                if sell_qty > 0:
                    self.log("signal", f"TP nivel {i+1}: +{level}%, vendiendo {sell_qty}")
                    self._sell_partial(sell_qty, f"take-profit-{level}pct")
                    with self.lock:
                        if i not in self.state["tp_hit_indices"]:
                            self.state["tp_hit_indices"].append(i)
                    return True
        return False

    def _check_dca(self):
        if not self.state.get("dca_active"):
            return
        with self.lock:
            if self.state["position_open"]:
                return
            last = self.state.get("last_dca_time")
            interval = self.state["dca_interval_minutes"]
        now = datetime.now(timezone.utc).isoformat()
        if not last:
            with self.lock:
                self.state["last_dca_time"] = now
            self.db.save_state(self.state)
            return
        try:
            last_dt = datetime.fromisoformat(last)
            now_dt = datetime.fromisoformat(now)
            elapsed_min = (now_dt - last_dt).total_seconds() / 60
            if elapsed_min >= interval:
                self.manual_buy()
                with self.lock:
                    self.state["last_dca_time"] = now
                self.db.save_state(self.state)
        except (ValueError, TypeError):
            with self.lock:
                self.state["last_dca_time"] = now

    def _step_threshold(self):
        price = self.get_live_price()
        if price is None:
            return
        with self.lock:
            buy_price = self.state["buy_price"]
            sell_price = self.state["sell_price"]
            stop_loss_enabled = self.state["stop_loss_enabled"]
            stop_loss_price = self.state["stop_loss_price"]
            position_open = self.state["position_open"]
        if position_open:
            if self._check_trailing_stop(price):
                return
            if self._check_take_profit(price):
                return
            if sell_price is not None and price >= sell_price:
                self.log("signal", f"Venta: {price} >= {sell_price}")
                self.manual_sell("take-profit")
                return
            if stop_loss_enabled and stop_loss_price is not None and price <= stop_loss_price:
                self.log("signal", f"Stop loss: {price} <= {stop_loss_price}")
                self.manual_sell("stop-loss")
                return
        elif buy_price is not None and price <= buy_price:
            self.log("signal", f"Compra: {price} <= {buy_price}")
            self.manual_buy()
            return

    def _step_indicator_strategy(self):
        strategy = self.state["strategy"]
        params = self.state.get("strategy_params", {})
        min_candles = STRATEGY_DEFS.get(strategy, {}).get("min_candles", 50)
        interval = self.state["chart_interval"]
        symbol = self.state["symbol"]

        klines = self.get_klines_raw(symbol, interval, limit=min_candles + 10)
        if not klines or len(klines) < min_candles:
            return

        closes = [c["close"] for c in klines]
        highs = [c["high"] for c in klines]
        lows = [c["low"] for c in klines]

        with self.lock:
            position_open = self.state["position_open"]

        if position_open:
            price = closes[-1]
            if self._check_trailing_stop(price):
                return
            if self._check_take_profit(price):
                return

        signal = eval_strategy(strategy, params, closes, highs, lows, position_open)
        if signal and signal["action"] == "buy":
            self.log("signal", f"Señal de compra: {signal.get('reason', '')}")
            try:
                self.manual_buy()
            except Exception as e:
                self.log("error", f"No se pudo comprar: {e}")
        elif signal and signal["action"] == "sell":
            self.log("signal", f"Señal de venta: {signal.get('reason', '')}")
            try:
                self.manual_sell(signal.get("reason", "strategy"))
            except Exception as e:
                self.log("error", f"No se pudo vender: {e}")

    def get_trade_history(self, limit=50):
        return self.db.get_trades(session_id=self.session_id, limit=limit)

    def get_all_sessions(self):
        return self.db.get_sessions()

    def run_backtest(self, symbol, interval, strategy_name, strategy_params,
                     quote_amount=100, kline_limit=500):
        klines = self.get_klines_raw(symbol, interval, limit=kline_limit)
        if not klines:
            raise RuntimeError("No se pudieron obtener datos de mercado.")

        strat_def = STRATEGY_DEFS.get(strategy_name)
        if not strat_def:
            raise RuntimeError(f"Estrategia desconocida: {strategy_name}")

        min_candles = strat_def.get("min_candles", 1)
        if len(klines) < min_candles:
            raise RuntimeError(f"Se necesitan al menos {min_candles} velas para {strat_def['label']}")

        def evaluate_fn(closes, highs, lows, position_open):
            return eval_strategy(strategy_name, strategy_params, closes, highs, lows, position_open)

        return self.db.run_backtest(
            symbol=symbol,
            interval=interval,
            klines=klines,
            quote_amount=float(quote_amount),
            evaluate_fn=evaluate_fn,
        )

    def snapshot(self):
        if self._ensure_client():
            try:
                self.get_live_price()
            except Exception as exc:
                self.last_error = str(exc)

        balances = {}
        if self._ensure_client():
            try:
                balances = self.get_balances()
            except Exception as exc:
                self.last_error = str(exc)

        indicators = None
        if self._ensure_client():
            try:
                indicators = self.get_indicators()
            except Exception:
                pass

        with self.lock:
            base_asset = None
            quote_asset = None
            try:
                info = self.ensure_symbol_info(self.state["symbol"]) if self.is_ready() else {}
                base_asset = info.get("baseAsset")
                quote_asset = info.get("quoteAsset")
            except Exception:
                pass

            strat_label = STRATEGY_DEFS.get(self.state["strategy"], {}).get("label", self.state["strategy"])

            return {
                "symbol": self.state["symbol"],
                "quote_amount": self._decimal_to_float(self.state["quote_amount"]),
                "buy_price": self._decimal_to_float(self.state["buy_price"]),
                "sell_price": self._decimal_to_float(self.state["sell_price"]),
                "stop_loss_enabled": self.state["stop_loss_enabled"],
                "stop_loss_price": self._decimal_to_float(self.state["stop_loss_price"]),
                "strategy": self.state["strategy"],
                "strategy_label": strat_label,
                "strategy_params": self.state.get("strategy_params", {}),
                "mode": self.state["mode"],
                "bot_active": self.state["bot_active"],
                "last_price": self._decimal_to_float(self.state["last_price"]),
                "session_pnl": self._decimal_to_float(self.state["session_pnl"]),
                "operations_count": self.state["operations_count"],
                "position_open": self.state["position_open"],
                "position_qty": self._decimal_to_float(self.state["position_qty"]),
                "position_entry_price": self._decimal_to_float(self.state["position_entry_price"]),
                "position_quote_spent": self._decimal_to_float(self.state["position_quote_spent"]),
                "status": self.state["status"],
                "chart_interval": self.state["chart_interval"],
                "logs": self.state["logs"],
                "indicators": indicators,
                "balances": {
                    asset: {
                        "free": self._decimal_to_float(v["free"]),
                        "locked": self._decimal_to_float(v["locked"]),
                        "total": self._decimal_to_float(v["total"]),
                    }
                    for asset, v in balances.items()
                },
                "base_asset": base_asset,
                "quote_asset": quote_asset,
                "use_testnet": self.use_testnet,
                "real_orders_enabled": self.real_orders_enabled,
                "credentials_ready": self.is_ready(),
                "last_error": self.last_error,
                "trailing_stop_active": self.state["trailing_stop_active"],
                "trailing_stop_pct": self._decimal_to_float(self.state["trailing_stop_pct"]),
                "tp_active": self.state["tp_active"],
                "tp_levels": self.state["tp_levels"],
                "tp_allocations": self.state["tp_allocations"],
                "dca_active": self.state["dca_active"],
                "dca_amount": self._decimal_to_float(self.state["dca_amount"]),
                "dca_interval_minutes": self.state["dca_interval_minutes"],
            }
