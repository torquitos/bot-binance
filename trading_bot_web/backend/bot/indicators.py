import math


def sma(data, period):
    if len(data) < period:
        return None
    return sum(data[-period:]) / period


def sma_array(data, period):
    if len(data) < period:
        return []
    result = []
    cum = sum(data[:period])
    result.append(cum / period)
    for i in range(period, len(data)):
        cum += data[i] - data[i - period]
        result.append(cum / period)
    return result


def ema_array(data, period):
    if len(data) < period:
        return []
    k = 2.0 / (period + 1.0)
    result = sum(data[:period]) / period
    values = [result]
    for price in data[period:]:
        result = price * k + result * (1.0 - k)
        values.append(result)
    return values


def ema(data, period):
    vals = ema_array(data, period)
    return vals[-1] if vals else None


def rsi(data, period=14):
    if len(data) < period + 1:
        return None
    gains, losses = 0.0, 0.0
    for i in range(-period, 0):
        diff = data[i] - data[i - 1]
        if diff > 0:
            gains += diff
        else:
            losses -= diff
    avg_gain = gains / period
    avg_loss = losses / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def rsi_array(data, period=14):
    if len(data) < period + 1:
        return []
    values = []
    for i in range(period, len(data)):
        window = data[: i + 1]
        values.append(rsi(window, period))
    return values


def macd(data, fast=12, slow=26, signal=9):
    ema_fast = ema_array(data, fast)
    ema_slow = ema_array(data, slow)
    if not ema_fast or not ema_slow:
        return None, None, None

    macd_line = [f - s for f, s in zip(ema_fast[-len(ema_slow):], ema_slow)]
    if len(macd_line) < signal:
        return None, None, None

    signal_vals = ema_array(macd_line, signal)
    if not signal_vals:
        return None, None, None

    hist = macd_line[-1] - signal_vals[-1]
    return macd_line[-1], signal_vals[-1], hist


def macd_array(data, fast=12, slow=26, signal=9):
    ema_fast = ema_array(data, fast)
    ema_slow = ema_array(data, slow)
    if not ema_fast or not ema_slow:
        return [], [], []

    macd_line = [f - s for f, s in zip(ema_fast[-len(ema_slow):], ema_slow)]
    if len(macd_line) < signal:
        return [], [], []

    signal_vals = ema_array(macd_line, signal)
    return macd_line, signal_vals, [m - s for m, s in zip(macd_line[-len(signal_vals):], signal_vals)]


def bollinger(data, period=20, std_dev=2.0):
    if len(data) < period:
        return None, None, None
    middle = sma(data[-period:], period)
    variance = sum((x - middle) ** 2 for x in data[-period:]) / period
    std = math.sqrt(variance)
    upper = middle + std_dev * std
    lower = middle - std_dev * std
    return upper, middle, lower


def compute_all(closes, fast_sma=10, slow_sma=30, rsi_period=14,
                macd_fast=12, macd_slow=26, macd_signal=9,
                bb_period=20, bb_std=2.0):
    return {
        "sma_fast": sma(closes, fast_sma),
        "sma_slow": sma(closes, slow_sma),
        "rsi": rsi(closes, rsi_period),
        "macd": macd(closes, macd_fast, macd_slow, macd_signal),
        "bollinger": bollinger(closes, bb_period, bb_std),
    }
