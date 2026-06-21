import os
import requests

TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"


class Notifier:
    def __init__(self):
        self.telegram_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        self.telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()

    def send(self, message):
        if self.telegram_token and self.telegram_chat_id:
            try:
                requests.post(
                    TELEGRAM_API.format(token=self.telegram_token),
                    json={
                        "chat_id": self.telegram_chat_id,
                        "text": message,
                        "parse_mode": "HTML",
                    },
                    timeout=5,
                )
            except Exception:
                pass

    def buy(self, symbol, quote, price, mode):
        emoji = "🟢" if mode == "SIMULACION" else "🟢"
        self.send(
            f"{emoji} <b>COMPRA EJECUTADA</b>\n"
            f"Par: {symbol}\nMonto: {quote} USDT\n"
            f"Precio: {price}\nModo: {mode}"
        )

    def sell(self, symbol, pnl, reason, mode):
        emoji = "🔴" if pnl < 0 else "🟢"
        self.send(
            f"{emoji} <b>VENTA EJECUTADA</b>\n"
            f"Par: {symbol}\nPnL: {pnl:.2f} USDT\n"
            f"Motivo: {reason}\nModo: {mode}"
        )

    def error(self, message):
        self.send(f"⚠️ <b>Error</b>\n{message}")

    def start(self, strategy, symbol):
        self.send(
            f"🤖 <b>Bot iniciado</b>\n"
            f"Estrategia: {strategy}\nPar: {symbol}"
        )

    def stop(self, reason="detenido"):
        self.send(f"⏹ <b>Bot {reason}</b>")
