# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV FLASK_APP=run.py
ENV FLASK_ENV=development

# Set the working directory in the container
WORKDIR /app

# Install system dependencies
# --- ΣΧΟΛΙΟ: Προσθήκη LibreOffice ---
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    libreoffice-writer \
    libreoffice-calc \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy the requirements file into the container at /app
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code into the container at /app
COPY . .

# Make port 5000 available
EXPOSE 5000

# Define the command to run on container start
CMD ["flask", "run", "--host=0.0.0.0", "--port=5000"]