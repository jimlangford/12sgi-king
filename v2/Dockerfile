FROM python:3.12-slim

WORKDIR /workspace

RUN apt-get update && apt-get install -y \
    git \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
    fastapi \
    uvicorn \
    huggingface_hub \
    requests \
    pydantic

COPY app /workspace/app

EXPOSE 8088

CMD ["python", "/workspace/app/main.py"]
