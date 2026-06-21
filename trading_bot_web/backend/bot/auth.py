import os
from functools import wraps

from flask import request, jsonify


def require_api_key(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        api_key = os.getenv("API_KEY", "").strip()
        if not api_key:
            return f(*args, **kwargs)

        key = request.headers.get("X-API-Key", "")
        if key != api_key:
            return jsonify({"ok": False, "error": "API Key inválida o ausente"}), 401
        return f(*args, **kwargs)

    return decorated
