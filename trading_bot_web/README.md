# QuantBot Pro — Binance Trading Bot

Bot de trading automatizado para **Binance Spot** con panel web profesional, estrategias basadas en indicadores técnicos, backtesting con compound, datos en tiempo real vía WebSocket y notificaciones Telegram.

## Tabla de Contenidos

- [Características](#caracteristicas)
- [Arquitectura](#arquitectura)
- [Requisitos](#requisitos)
- [Instalación Rápida](#instalacion-rapida)
  - [Windows (PowerShell)](#windows-powershell)
  - [Linux / macOS](#linux--macos)
  - [Docker](#docker)
- [Configuración](#configuracion)
  - [Variables de Entorno](#variables-de-entorno)
  - [Obtener API Keys de Binance](#obtener-api-keys-de-binance)
  - [Configurar Telegram (opcional)](#configurar-telegram-opcional)
  - [Configurar API_KEY de Seguridad (opcional)](#configurar-api_key-de-seguridad-opcional)
- [Uso](#uso)
  - [Abrir el Frontend](#abrir-el-frontend)
  - [Panel de Control](#panel-de-control)
  - [Operaciones Manuales](#operaciones-manuales)
  - [Bot Automático](#bot-automatico)
  - [Backtesting](#backtesting)
- [Estrategias](#estrategias)
  - [Umbral Simple](#umbral-simple)
  - [Cruce de SMA](#cruce-de-sma)
  - [RSI](#rsi)
  - [MACD](#macd)
  - [Bollinger Bands](#bollinger-bands)
  - [RSI + SMA](#rsi--sma)
- [Gestión de Riesgo (Fase 5)](#gestion-de-riesgo-fase-5)
  - [Trailing Stop](#trailing-stop)
  - [Take Profit Parcial](#take-profit-parcial)
  - [DCA (Compras Automáticas)](#dca-compras-automaticas)
- [Producción](#produccion)
  - [Checklist para Producción](#checklist-para-produccion)
  - [HTTPS / SSL](#https--ssl)
  - [Nginx Reverse Proxy](#nginx-reverse-proxy)
  - [Docker en Producción](#docker-en-produccion)
  - [Seguridad](#seguridad)
- [API REST](#api-rest)
  - [Endpoints Públicos](#endpoints-publicos)
  - [Endpoints Protegidos](#endpoints-protegidos)
  - [SSE Stream](#sse-stream)
- [Testing](#testing)
  - [Tests de Backend](#tests-de-backend)
  - [Tests de Frontend](#tests-de-frontend)
- [Solución de Problemas](#solucion-de-problemas)
- [Estructura del Proyecto](#estructura-del-proyecto)
- [Roadmap](#roadmap)

---

## Caracteristicas

### Trading
- **6 estrategias** configurables: Umbral, Cruce SMA, RSI, MACD, Bollinger Bands, RSI + SMA
- **Modo Manual**: Compra/venta con un clic
- **Modo Automático**: El bot opera solo según la estrategia seleccionada
- **Simulación**: Opera sin arriesgar fondos reales (ideal para pruebas)
- **Órdenes Reales**: Market buy/sell en Binance Spot (testnet o real)
- **Testnet**: Compatible con Binance Spot Testnet (fondos ficticios)

### Gestión de Riesgo
- **Stop Loss**: Precio fijo de salida automática
- **Trailing Stop**: Stop loss dinámico que sigue al precio
- **Take Profit Parcial**: Vende porcentajes de la posición en múltiples niveles
- **DCA (Dollar Cost Average)**: Compras periódicas automáticas

### Panel Web
- **Dashboard en vivo**: Precio, P&L, posición, balances actualizados por SSE
- **Gráfico profesional**: Velas OHLCV con lightweight-charts
- **Indicadores técnicos**: SMA, RSI, MACD, Bollinger Bands en tiempo real
- **Historial de trades**: Todas las operaciones con P&L
- **Sesiones de trading**: Múltiples sesiones con contadores independientes
- **Portafolio**: Balances detallados y curva de P&L
- **Responsive**: Funciona en desktop y móvil
- **Dark mode**: UI profesional estilo trading

### Backtesting
- Prueba cualquier estrategia contra datos históricos reales de Binance
- **Compound**: Reinversión automática de ganancias
- **Stop-loss configurable**: Porcentaje de emergencia personalizable
- Reportes detallados: P&L, win rate, drawdown, equity final
- Simulación de cada trade individual

### Infraestructura
- **WebSocket**: Precios en tiempo real vía Binance WebSocket
- **SSE**: Push de estado al frontend en tiempo real
- **SQLite**: Persistencia de configuración, trades y sesiones
- **Docker**: Listo para contenedorización
- **Rate limiting**: 2000 requests/hora por IP
- **CORS configurable**: Orígenes permitidos personalizables

---

## Arquitectura

```
┌─────────────┐     SSE (push)     ┌──────────────┐
│   Frontend   │ ◄──────────────── │   Backend     │
│  (HTML/CSS/  │                   │  Flask/Gunicorn│
│   JS/Chart)  │ ──── REST ──────► │   :5000       │
└─────────────┘                   └──────┬───────┘
                                         │
                              ┌──────────┼──────────┐
                              │          │          │
                         ┌────▼──┐ ┌────▼──┐ ┌─────▼──┐
                         │Binance│ │SQLite │ │Telegram │
                         │  WS   │ │  DB   │ │ (opt.)  │
                         └───────┘ └───────┘ └─────────┘
```

**Flujo de datos en automático:**
1. Binance WebSocket envía precios en tiempo real
2. `step_auto()` evalúa la estrategia cada 3 segundos
3. Si hay señal, ejecuta orden (simulada o real)
4. Persiste en SQLite y notifica por Telegram
5. SSE empuja el nuevo estado al frontend

---

## Requisitos

- **Python 3.10+** (probado en 3.11)
- **Cuenta Binance** (gratis, para API keys)
- Opcional: **Docker** (para despliegue contenerizado)
- Opcional: **Bot de Telegram** (para notificaciones)
- Opcional: **OpenSSL** (para HTTPS auto-generado)

---

## Instalacion Rapida

### Windows (PowerShell)

```powershell
# 1. Clonar el repositorio
git clone https://github.com/torquitos/bot-binance.git
cd bot-binance/trading_bot_web

# 2. Crear y activar entorno virtual
python -m venv .venv
.venv\Scripts\Activate.ps1

# 3. Instalar dependencias
cd backend
pip install -r requirements.txt

# 4. Configurar credenciales
# Editar backend/.env con tus API keys de Binance
notepad .env

# 5. Iniciar
python app.py
```

### Linux / macOS

```bash
# 1. Clonar
git clone https://github.com/torquitos/bot-binance.git
cd bot-binance/trading_bot_web

# 2. Entorno virtual
python3 -m venv .venv
source .venv/bin/activate

# 3. Dependencias
cd backend
pip install -r requirements.txt

# 4. Configurar
cp .env.example .env   # o editar el .env existente
nano .env

# 5. Iniciar
python app.py
```

### Docker

```bash
# Usando docker-compose (recomendado)
cd trading_bot_web
docker compose up --build

# O manualmente
cd trading_bot_web/backend
docker build -t trading-bot .
docker run -p 5000:5000 --env-file .env trading-bot
```

El backend arranca en `http://localhost:5000`.

---

## Configuracion

### Variables de Entorno

Editar `backend/.env`:

| Variable | Obligatorio | Default | Descripción |
|----------|-------------|---------|-------------|
| `BINANCE_API_KEY` | ✅ | — | API Key de Binance |
| `BINANCE_API_SECRET` | ✅ | — | Secret Key de Binance |
| `BINANCE_USE_TESTNET` | ❌ | `true` | `true` = Testnet (fondos ficticios), `false` = Producción (dinero real) |
| `BINANCE_ENABLE_REAL_ORDERS` | ❌ | `false` | `true` = Envía órdenes reales a Binance. `false` = Simulación local |
| `DEFAULT_SYMBOL` | ❌ | `BTCUSDT` | Par por defecto al iniciar |
| `DEFAULT_QUOTE_AMOUNT` | ❌ | `100` | Monto por operación en USDT |
| `FLASK_ENV` | ❌ | `development` | `development` = modo debug, `production` = sin debug |
| `SECRET_KEY` | ❌ | _(auto)_ | Clave para firmar sesiones Flask. Si se deja vacío, se genera automáticamente |
| `PORT` | ❌ | `5000` | Puerto del servidor |
| `CORS_ORIGINS` | ❌ | `http://localhost:5000,http://127.0.0.1:5000` | Orígenes permitidos para CORS (separados por coma) |
| `API_KEY` | ❌ | _(vacio)_ | Si se define, protege endpoints POST con header `X-API-Key` |
| `TELEGRAM_BOT_TOKEN` | ❌ | _(vacio)_ | Token del bot de Telegram |
| `TELEGRAM_CHAT_ID` | ❌ | _(vacio)_ | Chat ID de Telegram |
| `SSL_ENABLED` | ❌ | `false` | `true` = habilita HTTPS con cert auto-generado |
| `SSL_CERT` | ❌ | `cert.pem` | Ruta al certificado SSL |
| `SSL_KEY` | ❌ | `key.pem` | Ruta a la clave privada SSL |

### Obtener API Keys de Binance

**Testnet (recomendado para pruebas):**
1. Ir a [Binance Spot Testnet](https://testnet.binance.vision/)
2. Iniciar sesión con cuenta de GitHub
3. Ir a "API Keys" → "Create API Key"
4. Copiar `API Key` y `Secret Key`
5. El testnet provee **10,000 USDT** y **1 BTC** de fondos ficticios

**Producción (solo cuando estés listo):**
1. Ir a [Binance API Management](https://www.binance.com/en/my/settings/api-management)
2. Crear nueva API Key
3. Restringir a la IP del servidor donde correrá el bot
4. Deshabilitar retiros (solo trading)
5. Guardar Secret Key de forma segura

### Configurar Telegram (opcional)

1. Hablar con [@BotFather](https://t.me/BotFather) en Telegram
2. Crear nuevo bot → copiar el token
3. Hablar con [@userinfobot](https://t.me/userinfobot) para obtener tu chat ID
4. Poner ambos en `.env`:
```
TELEGRAM_BOT_TOKEN=123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11
TELEGRAM_CHAT_ID=123456789
```

### Configurar API_KEY de Seguridad (opcional)

Si defines `API_KEY` en `.env`, todos los endpoints POST la requerirán:

```bash
# Llamada con api key
curl -X POST http://localhost:5000/api/manual/buy \
  -H "X-API-Key: tu-api-key"
```

Si `API_KEY` está vacío, los endpoints POST no requieren autenticación.

---

## Uso

### Abrir el Frontend

El backend sirve los archivos estáticos automáticamente. Solo abre:

```
http://localhost:5000
```

**Alternativa**: Si quieres usar un servidor separado:

```bash
cd trading_bot_web/frontend
python -m http.server 8080
# luego editar frontend/config.js con API_BASE_URL: "http://127.0.0.1:5000"
```

### Panel de Control

El frontend tiene 4 pestañas:

**Dashboard**: Precio en vivo, posición actual, P&L, balances, bot card con controles (Buy/Sell/Auto), gráfico de velas, indicadores técnicos y stepper de configuración.

**Estrategias**: Selector de estrategia, parámetros y backtesting.

**Historial**: Trades realizados y sesiones de trading. Botón "+ Nueva sesión" para reiniciar contadores.

**Portafolio**: Balances detallados, curva de P&L acumulado.

### Operaciones Manuales

Desde la **bot card** en el Dashboard:

1. Asegúrate de que el bot esté **detenido** (status badge dice "Manual" o "En espera")
2. Configura el par, estrategia y parámetros en el stepper (pestaña Dashboard)
3. Haz clic en "Confirmar y Guardar"
4. Usa **COMPRAR** para abrir posición, **VENDER** para cerrarla
5. Alternativamente, haz clic en el pill **"MANUAL"** en la topbar para alternar a automático

### Bot Automatico

1. Configura todo en el stepper
2. Haz clic en **"INICIAR AUTO"** (o en el pill de modo en la topbar)
3. El bot evalúa la estrategia cada 3 segundos y opera automáticamente
4. Para detener: haz clic en **"DETENER"** o en el pill nuevamente

**Importante**: No puedes cambiar la configuración mientras el bot está activo. Debes detenerlo primero.

### Backtesting

1. Ve a la pestaña **Estrategias**
2. Haz clic en **"Mostrar"** para desplegar el panel de backtesting
3. Selecciona: par, intervalo, estrategia, parámetros, monto y cantidad de velas
4. Opcional: activa **"Compound"** para reinversión automática de ganancias
5. Haz clic en **"Ejecutar"**
6. Resultados: P&L, retorno %, win rate, drawdown, equity final y lista de trades

---

## Estrategias

### Umbral Simple

Compra cuando el precio cae a tu objetivo, vende cuando sube al objetivo.

| Parámetro | Tipo | Default | Descripción |
|-----------|------|---------|-------------|
| `buy_price` | float | — | Precio de compra (obligatorio) |
| `sell_price` | float | — | Precio de venta (obligatorio) |

### Cruce de SMA

Compra cuando la SMA rápida cruza **por encima** de la lenta (señal alcista). Vende cuando cruza **por debajo** (señal bajista).

| Parámetro | Tipo | Default | Descripción |
|-----------|------|---------|-------------|
| `fast_period` | int | 10 | Periodo de la SMA rápida |
| `slow_period` | int | 30 | Periodo de la SMA lenta |

### RSI

Compra cuando RSI está en zona de **sobreventa**. Vende cuando está en **sobrecompra**.

| Parámetro | Tipo | Default | Descripción |
|-----------|------|---------|-------------|
| `period` | int | 14 | Periodo del RSI |
| `oversold` | int | 30 | Límite de sobreventa (compra si RSI < este valor) |
| `overbought` | int | 70 | Límite de sobrecompra (vende si RSI > este valor) |

### MACD

Compra cuando la línea MACD cruza **por encima** de la línea de señal. Vende cuando cruza **por debajo**.

| Parámetro | Tipo | Default | Descripción |
|-----------|------|---------|-------------|
| `fast` | int | 12 | Periodo de la EMA rápida |
| `slow` | int | 26 | Periodo de la EMA lenta |
| `signal` | int | 9 | Periodo de la línea de señal |

### Bollinger Bands

Compra cuando el precio toca la **banda inferior**. Vende cuando toca la **banda superior**.

| Parámetro | Tipo | Default | Descripción |
|-----------|------|---------|-------------|
| `period` | int | 20 | Periodo de la SMA central |
| `std_dev` | float | 2.0 | Desviaciones estándar para las bandas |

### RSI + SMA

Compra si RSI está sobreventa **Y** el precio está por encima de la SMA de tendencia (filtro de tendencia alcista).

| Parámetro | Tipo | Default | Descripción |
|-----------|------|---------|-------------|
| `rsi_period` | int | 14 | Periodo del RSI |
| `rsi_oversold` | int | 30 | Límite de sobreventa |
| `rsi_overbought` | int | 70 | Límite de sobrecompra |
| `sma_period` | int | 200 | Periodo de la SMA de tendencia |

---

## Gestion de Riesgo (Fase 5)

### Trailing Stop

Stop loss dinámico que se ajusta automáticamente cuando el precio sube.

- **Activar**: Toggle "Trailing Stop" en el stepper (Paso 3)
- **Distancia**: Porcentaje desde el precio máximo alcanzado (ej: 2%)
- **Cómo funciona**: Si el precio sube a $100 y el trailing es 2%, el stop se coloca en $98. Si el precio sube a $110, el stop sube a $107.80. Si el precio cae a $107.80 o menos, se vende automáticamente.

### Take Profit Parcial

Vende porcentajes de tu posición en múltiples niveles de ganancia.

- **Activar**: Toggle "Take Profit Parcial"
- **Niveles (%)**: Porcentajes de ganancia para vender. Default: `3,5,10` (vende al +3%, +5%, +10%)
- **Asignaciones (%)**: Porcentaje de la posición a vender en cada nivel. Default: `33,33,34` (vende 33% en cada nivel)

### DCA (Compras Automáticas)

Realiza compras periódicas automáticas cuando no hay posición abierta.

- **Activar**: Toggle "DCA"
- **Monto (USDT)**: Cantidad a comprar en cada intervalo
- **Intervalo (min)**: Minutos entre cada compra automática

---

## Produccion

### Checklist para Produccion

- [ ] `BINANCE_USE_TESTNET=false` (deshabilita testnet)
- [ ] `BINANCE_ENABLE_REAL_ORDERS=true` (habilita órdenes reales)
- [ ] `API_KEY` definida (protege endpoints POST)
- [ ] `FLASK_ENV=production` (deshabilita modo debug)
- [ ] `CORS_ORIGINS` restringido a tu dominio
- [ ] HTTPS configurado (ver abajo)
- [ ] `TELEGRAM_BOT_TOKEN` y `TELEGRAM_CHAT_ID` configurados
- [ ] Probado con montos pequeños primero
- [ ] Monitoreo de logs configurado

### HTTPS / SSL

**Opción 1: Flask con cert auto-generado**

```bash
cd backend
SSL_ENABLED=true python app.py
```

Genera automáticamente `cert.pem` y `key.pem` con OpenSSL.

**Opción 2: Nginx reverse proxy (recomendado para producción)**

```nginx
# /etc/nginx/sites-available/trading-bot
server {
    listen 443 ssl;
    server_name tu-dominio.com;

    ssl_certificate /etc/letsencrypt/live/tu-dominio.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/tu-dominio.com/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Necesario para SSE
        proxy_buffering off;
        proxy_cache off;
    }
}
```

### Nginx Reverse Proxy

Para producción con Docker + nginx:

```yaml
# docker-compose.prod.yml
version: "3.8"
services:
  bot:
    build: ./backend
    container_name: trading-bot
    env_file: ./backend/.env
    volumes:
      - ./backend/data:/app/data
    restart: unless-stopped
    networks:
      - internal

  nginx:
    image: nginx:alpine
    ports:
      - "443:443"
      - "80:80"
    volumes:
      - ./nginx.conf:/etc/nginx/conf.d/default.conf
      - ./ssl:/etc/nginx/ssl
    depends_on:
      - bot
    networks:
      - internal

networks:
  internal:
    driver: bridge
```

### Docker en Produccion

```bash
# Construir y ejecutar
cd trading_bot_web
docker compose up --build -d

# Ver logs
docker compose logs -f

# Detener
docker compose down
```

### Seguridad

| Riesgo | Mitigación |
|--------|------------|
| API Key expuesta | El `.env` está en `.gitignore`. Nunca commits. |
| Acceso no autorizado a API | Definir `API_KEY` en `.env` y enviar header `X-API-Key` |
| CORS abierto | Configurar `CORS_ORIGINS` con los dominios específicos |
| Sin HTTPS | Usar nginx con Let's Encrypt o SSL auto-generado |
| Inyección SQL | SQLite con queries parametrizadas (seguro) |
| Secret Key débil | Se genera automáticamente con `secrets.token_hex(32)` |

---

## API REST

### Endpoints Publicos

| Método | Ruta | Descripción | Rate Limit |
|--------|------|-------------|------------|
| `GET` | `/api/health` | Health check del backend | ❌ Exento |
| `GET` | `/api/state` | Estado completo del bot (precio, posición, balances, indicadores, logs) | ❌ Exento |
| `GET` | `/api/stream` | **SSE** — Estado en tiempo real (streaming) | ❌ Exento |
| `GET` | `/api/logs` | Últimas entradas del log | ❌ Exento |
| `GET` | `/api/ticker?symbol=BTCUSDT` | Precio actual de un símbolo | 2000/h |
| `GET` | `/api/market/options` | Símbolos e intervalos disponibles | ❌ Exento |
| `GET` | `/api/market/klines?symbol=BTCUSDT&interval=15m&limit=80` | Datos de velas OHLCV | ❌ Exento |
| `GET` | `/api/strategies` | Definiciones de estrategias disponibles | ❌ Exento |
| `GET` | `/api/trades?limit=50` | Historial de operaciones | ❌ Exento |
| `GET` | `/api/sessions` | Sesiones de trading | ❌ Exento |

### Endpoints Protegidos

*Requieren `X-API-Key` header si `API_KEY` está definida en `.env`.*

| Método | Ruta | Body (JSON) | Descripción |
|--------|------|-------------|-------------|
| `POST` | `/api/config` | `{symbol, quote_amount, strategy, strategy_params, ...}` | Actualizar configuración del bot |
| `POST` | `/api/manual/buy` | — | Compra manual (market) |
| `POST` | `/api/manual/sell` | — | Venta manual (market) |
| `POST` | `/api/auto/start` | *(opcional: config)* | Iniciar bot automático |
| `POST` | `/api/auto/stop` | — | Detener bot automático |
| `POST` | `/api/backtest` | `{symbol, interval, strategy, strategy_params, quote_amount, kline_limit, compound, emergency_stop_pct}` | Ejecutar backtest |
| `POST` | `/api/session/new` | — | Crear nueva sesión (reinicia contadores) |
| `POST` | `/api/logs/clear` | — | Limpiar registro de actividad |
| `POST` | `/api/credentials` | `{api_key, api_secret, use_testnet}` | Actualizar credenciales en caliente |

### SSE Stream

El endpoint `/api/stream` envía el estado completo del bot cada 1 segundo:

```
GET /api/stream
Accept: text/event-stream

data: {"symbol":"BTCUSDT","last_price":64200.00,"bot_active":true,...}
```

Usado por el frontend para actualización en tiempo real. Implementa **reconexión automática** con backoff exponencial (1s → 30s max) y se **pausa** automáticamente cuando la pestaña está oculta (Page Visibility API).

---

## Testing

### Tests de Backend

```bash
cd trading_bot_web/backend
python -m pytest tests/ -v
```

**49 tests** que cubren:
- API endpoints (16 tests)
- Base de datos (6 tests)
- Indicadores técnicos (8 tests)
- Fase 5 — Trailing stop, TP, DCA (10 tests)
- Estrategias (5 tests)

### Tests de Frontend

```bash
# Abrir en navegador
cd trading_bot_web/frontend
start tests.html    # Windows
open tests.html     # macOS
```

**9 tests** que cubren: `toMoney`, `toShort`, `formatPair`, `validatePrices`.

---

## Solucion de Problemas

### "No module named 'bot'"

```bash
cd backend
pip install -e .
# O simplemente asegúrate de ejecutar python app.py desde backend/
```

### "threads can only be started once"

Ocurre al cambiar la configuración después de que el WebSocket ya se inició. Solucionado en `ws_manager.py` — el manager recrea el `ThreadedWebsocketManager` desde cero.

### El frontend no se conecta al backend

1. Verifica que el backend esté corriendo en `http://localhost:5000`
2. Abre `frontend/config.js` y verifica `API_BASE_URL`
3. Si usas un servidor separado para el frontend, configura CORS:
```
CORS_ORIGINS=http://localhost:8080,http://127.0.0.1:8080
```

### La pestaña History no funciona

Posible cache del navegador. Haz **Ctrl+F5** (hard refresh) para limpiar el cache de la página.

### "Error conectando a Binance"

1. Verifica que `BINANCE_API_KEY` y `BINANCE_API_SECRET` estén correctos en `.env`
2. Si usas testnet, asegúrate de que las keys sean de [testnet.binance.vision](https://testnet.binance.vision/)
3. Si usas producción, verifica que la IP esté en la whitelist de la API Key

### El backtest da 0 trades

1. Aumenta `kline_limit` (mínimo 100, recomendado 500)
2. Verifica que la estrategia tenga suficientes velas para sus indicadores
3. Algunas estrategias no generan señales en ciertos rangos de mercado

### El bot automático no compra/vende

1. Verifica que `credentials_ready` sea `true` en el state
2. Revisa los logs en el frontend para ver si hay señales
3. Para estrategias de indicadores, asegúrate de que haya suficientes velas
4. Comprueba que el stop loss/trailing stop no esté cerrando la posición inmediatamente

---

## Estructura del Proyecto

```
trading_bot_web/
├── README.md                          # Esta documentación
├── docker-compose.yml                 # Orquestación Docker
│
├── backend/
│   ├── app.py                         # API Flask (~20 endpoints)
│   ├── Dockerfile                     # Imagen Docker
│   ├── requirements.txt               # Dependencias Python
│   ├── .env                           # Credenciales (NO versionar)
│   ├── config.db                      # DB de tests (dejar fuera de git)
│   ├── data/
│   │   ├── bot.db                     # SQLite principal
│   │   └── activity.log               # Logs de actividad
│   │
│   ├── bot/
│   │   ├── __init__.py
│   │   ├── service.py                 # Lógica central del bot (917 líneas)
│   │   ├── database.py                # Persistencia SQLite
│   │   ├── strategies.py              # 6 estrategias + evaluador
│   │   ├── indicators.py              # SMA, EMA, RSI, MACD, Bollinger
│   │   ├── ws_manager.py              # WebSocket Binance Manager
│   │   ├── notifier.py                # Notificaciones Telegram
│   │   └── auth.py                    # Decorador de autenticación API Key
│   │
│   ├── tests/
│   │   ├── conftest.py                # Mocks globales (WSManager)
│   │   ├── test_api.py                # 16 tests de API
│   │   ├── test_database.py           # 6 tests de DB
│   │   ├── test_indicators.py         # 8 tests de indicadores
│   │   ├── test_phase5.py             # 10 tests de trailing/TP/DCA
│   │   └── test_strategies.py         # 5 tests de estrategias
│   │
│   └── .gitignore                     # Ignora .env y data/
│
└── frontend/
    ├── index.html                     # Panel web (571 líneas)
    ├── style.css                      # Estilos responsive dark (576 líneas)
    ├── app.js                         # Lógica frontend (864 líneas)
    ├── config.js                      # URL de la API
    ├── config.example.js              # Plantilla de configuración
    └── tests.html                     # Tests unitarios frontend (9 tests)
```

### Archivos Clave

| Archivo | Líneas | Responsabilidad |
|---------|--------|-----------------|
| `backend/bot/service.py` | 950+ | Orquestación: init, config, buy/sell, auto loop, trailing stop, TP, DCA, backtest, snapshot |
| `backend/bot/database.py` | 287 | SQLite: sessions, trades, config, backtest engine |
| `backend/bot/strategies.py` | 180 | 6 estrategias con evaluación individual |
| `backend/bot/indicators.py` | 119 | Cálculos: SMA, EMA, RSI, MACD, Bollinger |
| `backend/app.py` | 300+ | API Flask con rate limiting, CORS, SSE, SSL |
| `frontend/app.js` | 864 | Toda la lógica frontend: SSE, chart, render, backtest UI |

---

## Roadmap

- [x] Trading manual y automático
- [x] 6 estrategias de indicadores
- [x] Backtesting con compound
- [x] Trailing stop dinámico
- [x] Take profit parcial
- [x] DCA automático
- [x] Panel web responsive
- [x] Notificaciones Telegram
- [x] SSE en tiempo real
- [x] HTTPS auto-generado
- [x] Tests backend (49) y frontend (9)
- [x] Docker + docker-compose
- [x] Documentación completa
- [ ] Alertas por sonido en frontend
- [ ] Grid de pares favoritos configurables por usuario
- [ ] Múltiples bots simultáneos
- [ ] Soporte para múltiples exchanges (Bybit, OKX)
- [ ] TradingView Webhook integration
- [ ] Dashboard de rendimiento histórico con charts

---

## Advertencia

**Este bot opera con dinero real si configuras `BINANCE_USE_TESTNET=false` y `BINANCE_ENABLE_REAL_ORDERS=true`.**

El trading de criptomonedas conlleva **riesgo de pérdida total del capital**. Este software se proporciona "tal cual", sin garantías de ningún tipo. El autor no se responsabiliza por pérdidas financieras.

**→ Lee el [DESCARGO DE RESPONSABILIDAD](./DISCLAIMER.md) completo antes de usar este software.**

**Siempre:**
1. Prueba primero en **Testnet** hasta entender el comportamiento
2. Empieza con **montos pequeños** que puedas perder
3. Monitorea el bot regularmente
4. Nunca inviertas dinero que no puedas permitirte perder

---

*QuantBot Pro v1.0 — [torquitos/bot-binance](https://github.com/torquitos/bot-binance)*