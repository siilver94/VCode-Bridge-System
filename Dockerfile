# Simple, production-friendly Dockerfile for Streamlit
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8501

WORKDIR /app

# (Optional) system deps; wheels usually cover pandas/Pillow, but keep minimal build tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install -r requirements.txt

# Copy only source code; data and images are mounted at runtime
COPY ./*.py ./ 
COPY utils ./utils
COPY notebooks ./notebooks

# Mount points inside the container
RUN mkdir -p /app/data /app/images
VOLUME ["/app/data", "/app/images"]

EXPOSE 8501

# Run Streamlit
CMD ["bash", "-lc", "streamlit run app.py --server.port ${PORT} --server.address 0.0.0.0"]
