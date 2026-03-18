FROM python:3.11-slim

# System dependencies for CairoSVG (SVG rendering)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libcairo2 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf2.0-0 \
    libffi-dev \
    shared-mime-info \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create data directory (will be overridden by volume mount in production)
RUN mkdir -p /data /app/logs

# Default env vars (overridden by fly.toml / fly secrets)
ENV PORT=8080
ENV DATABASE_DIR=/data
ENV TIMING_MODE=scheduled

EXPOSE 8080

CMD ["python", "run_api.py"]
