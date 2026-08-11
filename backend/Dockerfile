FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./requirements.txt
COPY requirements-local-onnx.txt ./requirements-local-onnx.txt
COPY requirements-local-onnx-gpu.txt ./requirements-local-onnx-gpu.txt
ARG INSTALL_LOCAL_EMBEDDING=true
ARG LOCAL_EMBEDDING_RUNTIME=cpu
RUN pip install --no-cache-dir -r requirements.txt \
    && if [ "$INSTALL_LOCAL_EMBEDDING" = "true" ]; then \
         pip install --no-cache-dir --no-deps --index-url https://download.pytorch.org/whl/cpu torch==2.13.0+cpu \
         && pip install --no-cache-dir --no-deps sentence-transformers==5.7.0 \
         && if [ "$LOCAL_EMBEDDING_RUNTIME" = "gpu" ]; then \
              pip install --no-cache-dir -r requirements-local-onnx-gpu.txt; \
            elif [ "$LOCAL_EMBEDDING_RUNTIME" = "cpu" ]; then \
              pip install --no-cache-dir -r requirements-local-onnx.txt; \
            else \
              echo "Unsupported LOCAL_EMBEDDING_RUNTIME: $LOCAL_EMBEDDING_RUNTIME" >&2; exit 1; \
            fi \
         && pip install --no-cache-dir --no-deps optimum==2.1.0 optimum-onnx==0.1.0; \
       fi

COPY app ./app
COPY migrations ./migrations

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=5s --start-period=10s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
