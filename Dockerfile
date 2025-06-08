FROM python:3.11-slim

# Install ffmpeg
RUN apt-get update && \
    apt-get install -y ffmpeg && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements first to leverage Docker cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app
ENV NON_INTERACTIVE=True
# CMD ["python", "src/media_scanner.py"] # Old command
CMD ["python", "src/main.py", "--help"] # New command, runs CLI help