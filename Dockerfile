# Base image Python
FROM python:3.10-slim

# Set working directory
WORKDIR /src

# Copy requirements và cài đặt
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy toàn bộ code vào container
COPY . .

# Expose port cho FastAPI
EXPOSE 8000

# Chạy ứng dụng với Uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
