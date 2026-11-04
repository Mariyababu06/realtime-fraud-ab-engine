FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app
WORKDIR /app
COPY requirements.txt dashboard/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt -r dashboard/requirements.txt
COPY . .
# run as a non-root user
RUN useradd --create-home --uid 10001 appuser && mkdir -p /app/logs && chown -R appuser /app/logs
USER appuser
EXPOSE 8501
CMD ["python", "-m", "pipeline.consumer_processor"]
