FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 \
    DATA_DIR=/data FASTEMBED_CACHE_PATH=/data/models
WORKDIR /app

COPY requirements.txt requirements-optional.txt ./
# EXTRAS=true adds Milvus, Azure AI Search, Document Intelligence, Azure Monitor and spaCy support.
ARG EXTRAS=false
RUN pip install -r requirements.txt \
 && if [ "$EXTRAS" = "true" ]; then pip install -r requirements-optional.txt; fi

COPY app ./app
COPY samples ./samples
RUN useradd --create-home --uid 10001 askwise && mkdir -p /data && chown askwise /data
USER askwise

EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=3s --start-period=30s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
