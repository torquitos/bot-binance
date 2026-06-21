from bot.indicators import sma, rsi, macd, bollinger, sma_array, rsi_array, macd_array


STRATEGY_DEFS = {
    "threshold": {
        "label": "Umbral simple",
        "description": "Compra si el precio cae a tu objetivo, vende si sube al objetivo.",
        "params": {
            "buy_price": {"label": "Precio de compra", "type": "float", "default": None, "required": True},
            "sell_price": {"label": "Precio de venta", "type": "float", "default": None, "required": True},
            "stop_loss_price": {"label": "Stop Loss", "type": "float", "default": None, "required": False},
        },
        "min_candles": 1,
    },
    "sma_crossover": {
        "label": "Cruce de SMA",
        "description": "Compra cuando la SMA rápida cruza arriba de la lenta (alcista). Vende cuando cruza abajo (bajista).",
        "params": {
            "fast_period": {"label": "Periodo rápido", "type": "int", "default": 10, "required": True},
            "slow_period": {"label": "Periodo lento", "type": "int", "default": 30, "required": True},
        },
        "min_candles": 30,
    },
    "rsi": {
        "label": "RSI",
        "description": "Compra cuando RSI está en zona de sobreventa. Vende cuando está en sobrecompra.",
        "params": {
            "period": {"label": "Periodo RSI", "type": "int", "default": 14, "required": True},
            "oversold": {"label": "Sobreventa (<)", "type": "int", "default": 30, "required": True},
            "overbought": {"label": "Sobrecompra (>)", "type": "int", "default": 70, "required": True},
        },
        "min_candles": 15,
    },
    "macd": {
        "label": "MACD",
        "description": "Compra cuando la línea MACD cruza arriba de la línea de señal. Vende cuando cruza abajo.",
        "params": {
            "fast": {"label": "EMA rápida", "type": "int", "default": 12, "required": True},
            "slow": {"label": "EMA lenta", "type": "int", "default": 26, "required": True},
            "signal": {"label": "Señal", "type": "int", "default": 9, "required": True},
        },
        "min_candles": 35,
    },
    "bollinger": {
        "label": "Bollinger Bands",
        "description": "Compra cuando el precio toca la banda inferior. Vende cuando toca la banda superior.",
        "params": {
            "period": {"label": "Periodo", "type": "int", "default": 20, "required": True},
            "std_dev": {"label": "Desviaciones estándar", "type": "float", "default": 2.0, "required": True},
        },
        "min_candles": 20,
    },
    "rsi_sma": {
        "label": "RSI + SMA (Filtro de tendencia)",
        "description": "Compra si RSI está sobreventa Y el precio está sobre la SMA (tendencia alcista).",
        "params": {
            "rsi_period": {"label": "Periodo RSI", "type": "int", "default": 14, "required": True},
            "rsi_oversold": {"label": "RSI Sobreventa (<)", "type": "int", "default": 30, "required": True},
            "rsi_overbought": {"label": "RSI Sobrecompra (>)", "type": "int", "default": 70, "required": True},
            "sma_period": {"label": "Periodo SMA (tendencia)", "type": "int", "default": 200, "required": True},
        },
        "min_candles": 200,
    },
}


def evaluate(strategy_name, params, closes, highs, lows, position_open):
    fn = _EVALUATORS.get(strategy_name)
    if not fn:
        return {"action": None}
    return fn(params, closes, highs, lows, position_open)


def _eval_threshold(params, closes, highs, lows, position_open):
    price = closes[-1]
    buy_price = params.get("buy_price")
    sell_price = params.get("sell_price")
    stop_loss = params.get("stop_loss_price")

    if not position_open and buy_price is not None and price <= buy_price:
        return {"action": "buy", "reason": f"Precio {price:.2f} <= {buy_price}"}
    if position_open and sell_price is not None and price >= sell_price:
        return {"action": "sell", "reason": f"Take profit: {price:.2f} >= {sell_price}"}
    if position_open and stop_loss is not None and price <= stop_loss:
        return {"action": "sell", "reason": f"Stop loss: {price:.2f} <= {stop_loss}"}
    return {"action": None}


def _eval_sma_crossover(params, closes, highs, lows, position_open):
    fast = int(params.get("fast_period", 10))
    slow = int(params.get("slow_period", 30))

    fast_sma = sma_array(closes, fast)
    slow_sma = sma_array(closes, slow)

    if len(fast_sma) < 2 or len(slow_sma) < 2:
        return {"action": None}

    if not position_open and fast_sma[-2] <= slow_sma[-2] and fast_sma[-1] > slow_sma[-1]:
        return {"action": "buy", "reason": f"SMA({fast}) cruzó arriba SMA({slow})"}
    if position_open and fast_sma[-2] >= slow_sma[-2] and fast_sma[-1] < slow_sma[-1]:
        return {"action": "sell", "reason": f"SMA({fast}) cruzó abajo SMA({slow})"}
    return {"action": None}


def _eval_rsi(params, closes, highs, lows, position_open):
    period = int(params.get("period", 14))
    oversold = float(params.get("oversold", 30))
    overbought = float(params.get("overbought", 70))

    rsi_val = rsi(closes, period)
    if rsi_val is None:
        return {"action": None}

    if not position_open and rsi_val < oversold:
        return {"action": "buy", "reason": f"RSI {rsi_val:.1f} < {oversold} (sobreventa)"}
    if position_open and rsi_val > overbought:
        return {"action": "sell", "reason": f"RSI {rsi_val:.1f} > {overbought} (sobrecompra)"}
    return {"action": None}


def _eval_macd(params, closes, highs, lows, position_open):
    fast = int(params.get("fast", 12))
    slow = int(params.get("slow", 26))
    signal = int(params.get("signal", 9))

    macd_line, signal_vals, hist = macd_array(closes, fast, slow, signal)
    if len(macd_line) < 2 or len(signal_vals) < 2:
        return {"action": None}

    if not position_open and macd_line[-2] <= signal_vals[-2] and macd_line[-1] > signal_vals[-1]:
        return {"action": "buy", "reason": "MACD cruzó arriba señal"}
    if position_open and macd_line[-2] >= signal_vals[-2] and macd_line[-1] < signal_vals[-1]:
        return {"action": "sell", "reason": "MACD cruzó abajo señal"}
    return {"action": None}


def _eval_bollinger(params, closes, highs, lows, position_open):
    period = int(params.get("period", 20))
    std_dev = float(params.get("std_dev", 2.0))
    price = closes[-1]

    upper, middle, lower = bollinger(closes, period, std_dev)
    if upper is None:
        return {"action": None}

    if not position_open and price <= lower:
        return {"action": "buy", "reason": f"Precio tocó banda inferior ({lower:.2f})"}
    if position_open and price >= upper:
        return {"action": "sell", "reason": f"Precio tocó banda superior ({upper:.2f})"}
    return {"action": None}


def _eval_rsi_sma(params, closes, highs, lows, position_open):
    rsi_period = int(params.get("rsi_period", 14))
    rsi_oversold = float(params.get("rsi_oversold", 30))
    rsi_overbought = float(params.get("rsi_overbought", 70))
    sma_period = int(params.get("sma_period", 200))
    price = closes[-1]

    rsi_val = rsi(closes, rsi_period)
    sma_val = sma(closes, sma_period)
    if rsi_val is None or sma_val is None:
        return {"action": None}

    if not position_open and rsi_val < rsi_oversold and price > sma_val:
        return {"action": "buy", "reason": f"RSI {rsi_val:.1f} < {rsi_oversold} y precio > SMA({sma_period})"}
    if position_open and rsi_val > rsi_overbought:
        return {"action": "sell", "reason": f"RSI {rsi_val:.1f} > {rsi_overbought}"}
    return {"action": None}


_EVALUATORS = {
    "threshold": _eval_threshold,
    "sma_crossover": _eval_sma_crossover,
    "rsi": _eval_rsi,
    "macd": _eval_macd,
    "bollinger": _eval_bollinger,
    "rsi_sma": _eval_rsi_sma,
}
