FROM python:3.10-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    nginx supervisor apache2-utils ca-certificates \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app
COPY nginx.conf /etc/nginx/nginx.conf
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf
COPY entrypoint.sh /entrypoint.sh

RUN chmod +x /entrypoint.sh && mkdir -p /app/.streamlit

EXPOSE 8000
ENV PYTHONUNBUFFERED=1 PORT=8000

ENTRYPOINT ["/entrypoint.sh"]
