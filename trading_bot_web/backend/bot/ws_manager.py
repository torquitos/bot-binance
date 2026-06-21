import logging

from binance import ThreadedWebsocketManager

logger = logging.getLogger(__name__)


class WSManager:
    def __init__(self, api_key="", api_secret="", testnet=False):
        self.api_key = api_key
        self.api_secret = api_secret
        self.testnet = testnet
        self.twm = None
        self._running = False

    def start(self):
        if self._running:
            return
        self._running = True
        self.twm = ThreadedWebsocketManager(
            api_key=self.api_key,
            api_secret=self.api_secret,
            testnet=self.testnet,
        )
        self.twm.start()

    def stop(self):
        self._running = False
        if self.twm:
            try:
                self.twm.stop()
            except Exception:
                pass

    def subscribe_ticker(self, symbol, callback):
        if not self.twm:
            return
        self.twm.start_symbol_ticker_socket(callback=callback, symbol=symbol)

    def subscribe_kline(self, symbol, interval, callback):
        if not self.twm:
            return
        self.twm.start_kline_socket(callback=callback, symbol=symbol, interval=interval)

    def update_symbol(self, symbol, callback):
        self.stop()
        self.start()
        self.subscribe_ticker(symbol, callback)
