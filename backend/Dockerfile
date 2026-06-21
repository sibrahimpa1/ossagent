FROM python:3.9-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Pin httpx before anthropic to avoid proxies kwarg breakage
COPY requirements.txt .
RUN pip install --no-cache-dir httpx==0.27.2 \
    && pip install --no-cache-dir -r requirements.txt \
    && python -c "import httpx; from anthropic import Anthropic; Anthropic(api_key='test', http_client=httpx.Client()); print('anthropic ok')"

# Code is volume-mounted in production; copy for local docker builds
COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
