FROM python:3.12-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1

# SECURITY: Patch OS packages to fix known CVEs
RUN apt-get update && \
    apt-get upgrade -y && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

# SECURITY: Create and switch to a non-root user
RUN useradd -m -u 1000 appuser
USER appuser

EXPOSE 5001

CMD ["python", "app.py"]
