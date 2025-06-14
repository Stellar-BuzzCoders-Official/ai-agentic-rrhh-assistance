FROM python:3.11-bookworm

WORKDIR /app

RUN apt-get update && \
    apt-get install -y \
    curl \
    gnupg2 \
    lsb-release \
    software-properties-common \
    git \
    procps && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN pip install nltk && \
    python3 -c "import nltk; nltk.download('punkt_tab')"

COPY ./doc_llama/ollama.py /usr/local/lib/python3.10/site-packages/langchain_community/embeddings/ollama.py

COPY app.py .
COPY src ./src

EXPOSE 5000

CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port 5000 --reload"]