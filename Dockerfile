FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && useradd -u 10001 -m appuser && mkdir /data && chown appuser:appuser /data
COPY --chown=appuser:appuser . .
USER appuser
ENV DATABASE=/data/logistics.db
EXPOSE 8080
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "1", "--threads", "4", "--access-logfile", "-", "app:create_app()"]
