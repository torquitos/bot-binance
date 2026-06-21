from bot.strategies import STRATEGY_DEFS, evaluate


def test_strategy_defs():
    assert "threshold" in STRATEGY_DEFS
    assert "rsi" in STRATEGY_DEFS
    assert "sma_crossover" in STRATEGY_DEFS
    assert "macd" in STRATEGY_DEFS
    assert "bollinger" in STRATEGY_DEFS
    assert "rsi_sma" in STRATEGY_DEFS

    for name, defn in STRATEGY_DEFS.items():
        assert "label" in defn
        assert "params" in defn
        assert "min_candles" in defn


def test_threshold_buy():
    closes = [100, 101, 99, 98, 97]
    signal = evaluate("threshold", {"buy_price": 98, "sell_price": 105}, closes, closes, closes, False)
    assert signal["action"] == "buy"


def test_threshold_sell():
    closes = [100, 101, 102, 103, 104]
    signal = evaluate("threshold", {"buy_price": 95, "sell_price": 103}, closes, closes, closes, True)
    assert signal["action"] == "sell"


def test_threshold_no_signal():
    closes = [100, 101, 102]
    signal = evaluate("threshold", {"buy_price": 95, "sell_price": 110}, closes, closes, closes, False)
    assert signal["action"] is None


def test_rsi_buy():
    closes = [44, 44.34, 44.09, 43.61, 44.33, 44.83, 45.10, 45.42, 45.84, 46.08,
              45.89, 46.03, 45.61, 46.28, 46.28, 46.00, 44.03, 43.41, 42.22, 41.64]
    signal = evaluate("rsi", {"period": 14, "oversold": 30, "overbought": 70}, closes, closes, closes, False)
    assert signal["action"] == "buy"


def test_unknown_strategy():
    signal = evaluate("non_existent", {}, [100], [100], [100], False)
    assert signal["action"] is None
