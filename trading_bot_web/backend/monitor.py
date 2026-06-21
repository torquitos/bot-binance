"""
Monitor de salud para QuantBot Pro.

Uso:
    python monitor.py                          # Una sola verificacion
    python monitor.py --watch                  # Verifica cada 60 segundos
    python monitor.py --watch --interval 30    # Cada 30 segundos
    python monitor.py --webhook https://...    # POST a webhook si algo falla

Requiere: requests (ya incluido en requirements.txt)
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime

try:
    import requests
except ImportError:
    requests = None


API_URL = os.getenv("MONITOR_API_URL", "http://127.0.0.1:5000")
WEBHOOK_URL = os.getenv("MONITOR_WEBHOOK_URL", "")


def check():
    results = {"timestamp": datetime.utcnow().isoformat(), "checks": [], "healthy": True}

    # 1. Health endpoint
    try:
        r = requests.get(f"{API_URL}/api/health", timeout=10)
        data = r.json()
        if data.get("ok"):
            results["checks"].append({
                "name": "health",
                "status": "ok",
                "detail": data.get("message"),
            })
        else:
            results["checks"].append({
                "name": "health",
                "status": "error",
                "detail": data.get("error", "unknown"),
            })
            results["healthy"] = False
    except Exception as e:
        results["checks"].append({
            "name": "health",
            "status": "fail",
            "detail": str(e),
        })
        results["healthy"] = False

    # 2. SSE stream alive check
    try:
        r = requests.get(f"{API_URL}/api/stream", stream=True, timeout=5)
        if r.status_code == 200:
            raw = r.raw.read(50, decode_content=False)
            if b"data:" in raw:
                results["checks"].append({
                    "name": "sse",
                    "status": "ok",
                    "detail": "Streaming data recibido",
                })
            else:
                results["checks"].append({
                    "name": "sse",
                    "status": "warning",
                    "detail": "Stream respondio pero sin data esperada",
                })
        else:
            results["checks"].append({
                "name": "sse",
                "status": "error",
                "detail": f"HTTP {r.status_code}",
            })
            results["healthy"] = False
        r.close()
    except Exception as e:
        results["checks"].append({
            "name": "sse",
            "status": "fail",
            "detail": str(e),
        })
        results["healthy"] = False

    # 3. State consistency
    try:
        r = requests.get(f"{API_URL}/api/state", timeout=15)
        data = r.json()
        state = data.get("state", {})
        checks = []
        if state.get("last_error"):
            checks.append(f"last_error: {state['last_error']}")
            results["healthy"] = False
        if state.get("last_price") is None:
            checks.append("last_price es None")
            results["healthy"] = False
        if state.get("bot_active") and state.get("position_open") is None:
            checks.append("bot activo sin estado de posicion claro")
            results["healthy"] = False
        results["checks"].append({
            "name": "state",
            "status": "ok" if not checks else "warning",
            "detail": "; ".join(checks) if checks else f"Precio: {state.get('last_price')}, "
                      f"Bot: {'ACTIVO' if state.get('bot_active') else 'DETENIDO'}, "
                      f"Posicion: {'ABIERTA' if state.get('position_open') else 'CERRADA'}, "
                      f"Ops: {state.get('operations_count', 0)}",
        })
    except Exception as e:
        results["checks"].append({
            "name": "state",
            "status": "fail",
            "detail": str(e),
        })
        results["healthy"] = False

    # 4. Log file size
    log_path = os.path.join(os.path.dirname(__file__), "data", "activity.log")
    try:
        sz = os.path.getsize(log_path)
        mb = sz / (1024 * 1024)
        if mb > 10:
            results["checks"].append({
                "name": "log_size",
                "status": "warning",
                "detail": f"{mb:.1f} MB (max recomendado: 10 MB, rotation activa)",
            })
        else:
            results["checks"].append({
                "name": "log_size",
                "status": "ok",
                "detail": f"{mb:.1f} MB",
            })
    except Exception as e:
        results["checks"].append({
            "name": "log_size",
            "status": "warning",
            "detail": f"No se pudo leer log: {e}",
        })

    return results


def send_webhook(results, url):
    if not url or not requests:
        return
    try:
        emoji = "✅" if results["healthy"] else "🚨"
        message = f"{emoji} QuantBot Monitor\n"
        message += f"Timestamp: {results['timestamp']}\n"
        message += f"Estado: {'SALUDABLE' if results['healthy'] else 'PROBLEMAS DETECTADOS'}\n\n"
        for c in results["checks"]:
            icon = {"ok": "✅", "warning": "⚠️", "error": "❌", "fail": "🚨"}.get(c["status"], "❓")
            message += f"{icon} {c['name']}: {c['detail']}\n"
        requests.post(url, json={"text": message}, timeout=10)
    except Exception:
        pass  # Silently ignore webhook errors


def print_results(results):
    status_icon = "✅" if results["healthy"] else "🚨"
    print(f"\n{status_icon} QuantBot Monitor — {results['timestamp']}")
    print(f"   Estado: {'SALUDABLE' if results['healthy'] else 'PROBLEMAS DETECTADOS'}\n")
    for c in results["checks"]:
        icon = {"ok": "  ✅", "warning": "  ⚠️", "error": "  ❌", "fail": "  🚨"}.get(c["status"], "  ❓")
        print(f"{icon} {c['name']}: {c['detail']}")
    print()


def main():
    parser = argparse.ArgumentParser(description="QuantBot Pro — Monitor de Salud")
    parser.add_argument("--watch", action="store_true", help="Modo vigilancia continua")
    parser.add_argument("--interval", type=int, default=60, help="Intervalo en segundos (default: 60)")
    parser.add_argument("--webhook", default=WEBHOOK_URL, help="URL de webhook para alertas")
    parser.add_argument("--json", action="store_true", help="Salida en JSON")
    args = parser.parse_args()

    if not requests:
        print("ERROR: requests no instalado. Ejecuta: pip install requests")
        sys.exit(1)

    while True:
        results = check()
        if args.json:
            print(json.dumps(results, indent=2))
        else:
            print_results(results)

        if results.get("checks"):
            last = results["checks"][0]
            if last["status"] in ("fail",):
                send_webhook(results, args.webhook)

        if not args.watch:
            break
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
