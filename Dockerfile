# Gunakan image Python resmi
FROM python:3.9-slim

# Set working directory
WORKDIR /app

# Copy file requirements
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy seluruh kode aplikasi
COPY . .

# Expose port
EXPOSE 5000

# Jalankan aplikasi
CMD ["python", "app.py"]
