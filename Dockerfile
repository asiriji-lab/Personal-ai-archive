FROM python:3.10-slim

WORKDIR /app

# Install system dependencies (e.g., for building sqlite-vec or other C extensions if needed)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Run the validation script on container startup (fails fast if env is bad)
# and then default to starting the MCP server or TUI.
CMD ["sh", "-c", "python setup_brain.py && python brain_server.py"]
