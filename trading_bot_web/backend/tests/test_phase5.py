from decimal import Decimal
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

from bot.service import TradingBotService


def test_service_init_no_keys():
    svc = TradingBotService()
    assert "trailing_stop_active" in svc.state
    assert "tp_active" in svc.state
    assert "dca_active" in svc.state
    assert "position_highest_price" in svc.state
    assert "tp_hit_indices" in svc.state
    assert "position_initial_qty" in svc.state


def test_trailing_stop_triggers():
    svc = TradingBotService()
    svc.state["trailing_stop_active"] = True
    svc.state["trailing_stop_pct"] = Decimal("5")
    svc.state["position_open"] = True
    svc.state["position_highest_price"] = Decimal("100")
    with patch.object(svc, "manual_sell") as mock_sell:
        result = svc._check_trailing_stop(Decimal("94"))
        assert result is True
        mock_sell.assert_called_once_with("trailing-stop")


def test_trailing_stop_no_trigger_above_stop():
    svc = TradingBotService()
    svc.state["trailing_stop_active"] = True
    svc.state["trailing_stop_pct"] = Decimal("5")
    svc.state["position_open"] = True
    svc.state["position_highest_price"] = Decimal("100")
    with patch.object(svc, "manual_sell") as mock_sell:
        result = svc._check_trailing_stop(Decimal("97"))
        assert result is False
        mock_sell.assert_not_called()


def test_trailing_stop_updates_highest():
    svc = TradingBotService()
    svc.state["trailing_stop_active"] = True
    svc.state["trailing_stop_pct"] = Decimal("5")
    svc.state["position_open"] = True
    svc.state["position_highest_price"] = Decimal("100")
    with patch.object(svc, "manual_sell") as mock_sell:
        result = svc._check_trailing_stop(Decimal("110"))
        assert result is False
        assert svc.state["position_highest_price"] == Decimal("110")
        mock_sell.assert_not_called()


def test_trailing_stop_inactive():
    svc = TradingBotService()
    svc.state["trailing_stop_active"] = False
    svc.state["position_open"] = True
    svc.state["position_highest_price"] = Decimal("100")
    with patch.object(svc, "manual_sell") as mock_sell:
        result = svc._check_trailing_stop(Decimal("50"))
        assert result is False
        mock_sell.assert_not_called()


def test_take_profit_triggers():
    svc = TradingBotService()
    svc.state["tp_active"] = True
    svc.state["position_open"] = True
    svc.state["position_entry_price"] = Decimal("100")
    svc.state["position_qty"] = Decimal("1.0")
    svc.state["position_initial_qty"] = Decimal("1.0")
    svc.state["tp_levels"] = "10"
    svc.state["tp_allocations"] = "50"
    svc.state["tp_hit_indices"] = []
    with patch.object(svc, "_sell_partial") as mock_sell:
        result = svc._check_take_profit(Decimal("110"))
        assert result is True
        mock_sell.assert_called_once()
        args = mock_sell.call_args[0]
        assert args[0] == Decimal("0.5")
        assert "take-profit" in args[1]


def test_take_profit_below_threshold():
    svc = TradingBotService()
    svc.state["tp_active"] = True
    svc.state["position_open"] = True
    svc.state["position_entry_price"] = Decimal("100")
    svc.state["position_qty"] = Decimal("1.0")
    svc.state["position_initial_qty"] = Decimal("1.0")
    svc.state["tp_levels"] = "10"
    svc.state["tp_allocations"] = "50"
    svc.state["tp_hit_indices"] = []
    with patch.object(svc, "_sell_partial") as mock_sell:
        result = svc._check_take_profit(Decimal("105"))
        assert result is False
        mock_sell.assert_not_called()


def test_take_profit_hit_level_not_retriggered():
    svc = TradingBotService()
    svc.state["tp_active"] = True
    svc.state["position_open"] = True
    svc.state["position_entry_price"] = Decimal("100")
    svc.state["position_qty"] = Decimal("0.5")
    svc.state["position_initial_qty"] = Decimal("1.0")
    svc.state["tp_levels"] = "5,10"
    svc.state["tp_allocations"] = "50,50"
    svc.state["tp_hit_indices"] = [0]
    with patch.object(svc, "_sell_partial") as mock_sell:
        result = svc._check_take_profit(Decimal("110"))
        assert result is True
        mock_sell.assert_called_once()
        args = mock_sell.call_args[0]
        assert args[0] == Decimal("0.5")


def test_take_profit_inactive():
    svc = TradingBotService()
    svc.state["tp_active"] = False
    svc.state["position_open"] = True
    svc.state["position_entry_price"] = Decimal("100")
    svc.state["tp_levels"] = "10"
    svc.state["tp_allocations"] = "100"
    with patch.object(svc, "_sell_partial") as mock_sell:
        result = svc._check_take_profit(Decimal("200"))
        assert result is False
        mock_sell.assert_not_called()


def test_dca_triggers_after_interval():
    svc = TradingBotService()
    svc.state["dca_active"] = True
    svc.state["dca_interval_minutes"] = 1
    svc.state["position_open"] = False
    past = datetime.now(timezone.utc).timestamp() - 120
    svc.state["last_dca_time"] = datetime.fromtimestamp(past, tz=timezone.utc).isoformat()
    with patch.object(svc, "manual_buy") as mock_buy:
        svc._check_dca()
        mock_buy.assert_called_once()


def test_dca_skips_when_position_open():
    svc = TradingBotService()
    svc.state["dca_active"] = True
    svc.state["dca_interval_minutes"] = 1
    svc.state["position_open"] = True
    svc.state["last_dca_time"] = "2000-01-01T00:00:00"
    with patch.object(svc, "manual_buy") as mock_buy:
        svc._check_dca()
        mock_buy.assert_not_called()


def test_dca_skips_before_interval():
    svc = TradingBotService()
    svc.state["dca_active"] = True
    svc.state["dca_interval_minutes"] = 60
    svc.state["position_open"] = False
    svc.state["last_dca_time"] = datetime.now(timezone.utc).isoformat()
    with patch.object(svc, "manual_buy") as mock_buy:
        svc._check_dca()
        mock_buy.assert_not_called()


def test_dca_inactive():
    svc = TradingBotService()
    svc.state["dca_active"] = False
    svc.state["position_open"] = False
    svc.state["last_dca_time"] = "2000-01-01T00:00:00"
    with patch.object(svc, "manual_buy") as mock_buy:
        svc._check_dca()
        mock_buy.assert_not_called()
