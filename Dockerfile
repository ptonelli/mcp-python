# Use Python 3.10 as base image
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Copy requirements file
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY server.py .

# Set environment variables (if needed)
ENV HOST=0.0.0.0

# Expose port (FastMCP typically uses port 8000 by default)
EXPOSE 8000

# Run the server
CMD ["python", "server.py"]
