FROM python:3.10-slim

WORKDIR /app

# Install system dependencies (ffmpeg is required for whisper/audio)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Upgrade pip and increase timeout settings
RUN pip install --upgrade pip

# Install PyTorch CPU-only version first (smaller and faster download)
# This avoids timeout issues with the large default PyTorch package
RUN pip install --no-cache-dir --default-timeout=300 \
    torch --index-url https://download.pytorch.org/whl/cpu

# Install remaining dependencies
RUN pip install --no-cache-dir --default-timeout=300 -r requirements.txt

COPY . .

# Expose port
EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
