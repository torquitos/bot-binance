FROM python:3.11-slim

RUN apt-get update -qq && apt-get install -y -qq openssl && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5000 5443

# Para desarrollo local: SSL auto-generado via python app.py con SSL_ENABLED=true
# Para produccion con Docker: usar nginx como reverse proxy para SSL termination
# (ver README para configuracion detallada)
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--worker-class", "eventlet", "--workers", "1", "--timeout", "120", "app:app"]
