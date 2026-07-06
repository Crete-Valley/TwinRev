# Use a lightweight Python image
FROM python:3.10-slim

# Set working directory inside container
WORKDIR /app

# Install system dependencies (CBC solver)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    coinor-cbc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy all project files into container
COPY . .

# Run as an unprivileged user; log + result output dirs must stay writable.
RUN useradd --uid 10001 --user-group --no-create-home --shell /usr/sbin/nologin app \
    && chown -R app:app /app
USER 10001

ENV PYTHONUNBUFFERED=1

# Expose FastAPI port
EXPOSE 8000

# Run FastAPI app (note: app.py is inside services/)
CMD ["uvicorn", "services.app:app", "--host=0.0.0.0", "--port=8000"]
