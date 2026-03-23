FROM python:3.12-slim

LABEL maintainer="online-radio-station"
LABEL description="Self-hosted online radio station with admin panel and synchronized streaming"

# Prevent Python from writing .pyc files and enable unbuffered output
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install dependencies first (layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create directories for data persistence
RUN mkdir -p /app/instance /app/app/static/uploads

# Expose the application port
EXPOSE 8000

# Default environment variables (override in docker-compose or at runtime)
ENV SECRET_KEY="change-me-in-production" \
    ADMIN_USERNAME="admin" \
    ADMIN_PASSWORD="admin123"

# Run with gunicorn for production
# Use --threads for concurrent streaming connections
CMD ["gunicorn", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "1", \
     "--threads", "16", \
     "--timeout", "0", \
     "--keep-alive", "65", \
     "run:app"]
