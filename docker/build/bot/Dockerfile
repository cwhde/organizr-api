# Use a recent slim Python image
FROM python:3.11-slim

# Prevent Python from buffering stdout/stderr
ENV PYTHONUNBUFFERED=1

# Set working directory
WORKDIR /app

# Copy and install Python dependencies
# We copy requirements.txt from the bot subfolder
COPY /bot/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Clean up the requirements file after installation
RUN rm requirements.txt

# Copy bot application code
COPY /bot .

# Start the application
ENTRYPOINT ["python", "app.py"]