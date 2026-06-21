import math
from bot.indicators import sma, ema, rsi, macd, bollinger, sma_array, ema_array


def test_sma():
    data = [10, 20, 30, 40, 50]
    assert sma(data, 3) == 40.0
    assert sma(data, 5) == 30.0
    assert sma([1, 2], 3) is None


def test_sma_array():
    data = [1, 2, 3, 4, 5]
    result = sma_array(data, 3)
    assert len(result) == 3
    assert result[0] == 2.0
    assert result[-1] == 4.0


def test_ema():
    data = [10, 11, 12, 13, 14]
    result = ema(data, 3)
    assert result is not None
    assert isinstance(result, float)


def test_rsi():
    data = [44, 44.34, 44.09, 43.61, 44.33, 44.83, 45.10, 45.42, 45.84, 46.08,
            45.89, 46.03, 45.61, 46.28, 46.28, 46.00, 46.03, 46.41, 46.22, 45.64]
    result = rsi(data, 14)
    assert result is not None
    assert 0 <= result <= 100


def test_rsi_short_data():
    assert rsi([1, 2, 3], 14) is None


def test_macd():
    data = [100 + math.sin(i * 0.5) * 10 for i in range(50)]
    macd_line, signal, hist = macd(data, 12, 26, 9)
    assert macd_line is not None
    assert signal is not None
    assert hist is not None


def test_bollinger():
    data = [100 + (i % 10) for i in range(30)]
    upper, middle, lower = bollinger(data, 20, 2.0)
    assert upper is not None
    assert middle is not None
    assert lower is not None
    assert upper >= middle >= lower


def test_bollinger_short_data():
    assert bollinger([1, 2], 20) == (None, None, None)
