# 🤖 Bot de Trading — Binance

Bot de trading automatizado para Binance Spot con panel web, estrategias basadas en indicadores técnicos, backtesting, notificaciones Telegram y datos en tiempo real vía WebSocket.

---

## ✨ Características

| Característica | Detalle |
|---|---|
| **Panel web** | UI interactiva con gráfico profesional (lightweight-charts), indicadores en vivo |
| **Estrategias** | Umbral, Cruce SMA, RSI, MACD, Bollinger Bands, RSI + SMA |
| **Backtesting** | Prueba cualquier estrategia contra datos históricos con reportes detallados |
| **Tiempo real** | WebSocket Binance para precios, SSE para push al frontend |
| **Persistencia** | SQLite — configuración, historial de trades y sesiones |
| **Notificaciones** | Telegram en cada compra/venta/error |
| **Simulación/Real** | Modo simulación sin riesgo o trading real con órdenes market |
| **Stop Loss** | Configurable por estrategia |
| **Testnet** | Compatible con Binance Spot Testnet |

---

## ⚙️ Estrategias disponibles

| Estrategia | Compra | Venta |
|---|---|---|
| **Umbral simple** | Precio ≤ objetivo | Precio ≥ objetivo (o stop loss) |
| **Cruce SMA** | SMA rápida cruza arriba de lenta | SMA rápida cruza abajo de lenta |
| **RSI** | RSI < sobreventa (ej: 30) | RSI > sobrecompra (ej: 70) |
| **MACD** | MACD cruza arriba de señal | MACD cruza abajo de señal |
| **Bollinger Bands** | Precio toca banda inferior | Precio toca banda superior |
| **RSI + SMA** | RSI < 30 y precio > SMA(200) | RSI > 70 |

---

## 🚀 Inicio rápido

### 1. Backend

```bash
cd trading_bot_web/backend
python -m venv .venv
.venv\Scripts\activate     # Windows
pip install -r requirements.txt
```

Crea `backend/.env`:

```env
FLASK_ENV=development
SECRET_KEY=change-me
BINANCE_API_KEY=tu_api_key
BINANCE_API_SECRET=tu_api_secret
BINANCE_USE_TESTNET=true
BINANCE_ENABLE_REAL_ORDERS=false
DEFAULT_SYMBOL=BTCUSDT
DEFAULT_QUOTE_AMOUNT=100
# Opcional — Telegram
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
```

Ejecuta:

```bash
python app.py
```

### 2. Frontend

Abre `trading_bot_web/frontend/index.html` con un servidor estático (Live Server, `python -m http.server`, etc.)

O simplemente abre el archivo directamente en el navegador.

La URL de la API se configura en `frontend/config.js`:

```js
window.APP_CONFIG = {
  API_BASE_URL: "http://127.0.0.1:5000",
};
```

---

## 📡 API endpoints

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/api/health` | Health check |
| GET | `/api/state` | Estado completo del bot |
| GET | `/api/stream` | SSE — estado en tiempo real |
| GET | `/api/ticker` | Precio actual de un símbolo |
| GET | `/api/market/options` | Símbolos e intervalos disponibles |
| GET | `/api/market/klines` | Datos de velas (OHLCV) |
| GET | `/api/strategies` | Definiciones de estrategias |
| GET | `/api/trades` | Historial de operaciones |
| GET | `/api/sessions` | Sesiones de trading |
| POST | `/api/config` | Actualizar configuración |
| POST | `/api/manual/buy` | Compra manual |
| POST | `/api/manual/sell` | Venta manual |
| POST | `/api/auto/start` | Iniciar bot automático |
| POST | `/api/auto/stop` | Detener bot automático |
| POST | `/api/backtest` | Ejecutar backtest |
| POST | `/api/logs/clear` | Limpiar registro |

---

## 🐳 Docker

```bash
cd trading_bot_web/backend
docker build -t trading-bot .
docker run -p 5000:5000 --env-file .env trading-bot
```

---

## 📁 Estructura del proyecto

```
trading_bot_web/
├── backend/
│   ├── app.py                 # API Flask (16 endpoints)
│   ├── requirements.txt
│   ├── .env                   # Credenciales (no versionar)
│   ├── bot/
│   │   ├── service.py         # Lógica principal del bot
│   │   ├── database.py        # SQLite — persistencia
│   │   ├── strategies.py      # Definiciones y evaluador de estrategias
│   │   ├── indicators.py      # Cálculo de indicadores (SMA, RSI, MACD, BB)
│   │   ├── ws_manager.py      # WebSocket Binance (precios en tiempo real)
│   │   └── notifier.py        # Notificaciones Telegram
│   └── data/
│       ├── activity.log       # Registro de actividad
│       └── bot.db             # Base de datos SQLite
└── frontend/
    ├── index.html             # Panel web
    ├── style.css              # Estilos oscuros
    ├── app.js                 # Lógica del frontend
    ├── config.js              # URL de la API
    └── config.example.js      # Plantilla de configuración
```

---

## 🛠️ Próximas mejoras

- [ ] Autenticación en la API
- [ ] Docker compose completo
- [ ] Trailing stop dinámico
- [ ] Take profit parcial por niveles
- [ ] Tests unitarios y de integración
- [ ] Soporte para múltiples exchanges
- [ ] Estrategia DCA / Grid trading

---

## ⚠️ Advertencia

Este bot es una herramienta educativa. Usar fondos reales implica riesgo de pérdida total. Prueba siempre primero en Testnet.
