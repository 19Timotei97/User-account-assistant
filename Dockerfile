# Use Python 3.8 slim image as a base
FROM python:3.8-slim

# Create a non-root user
RUN adduser --disabled-password --gecos '' --shell /bin/sh appuser

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file
COPY requirements.txt /app/

# Ensure the pip version is the same as the one used for development and install requirements
RUN python -m pip install --upgrade pip==24.2 && \
    pip install --no-cache-dir -r requirements.txt

# Copy the current directory contents into the container at /app
COPY app /app

# Set environment variable to ensure that Python app files
ENV PYTHONPATH=/app

# Switch to the non-root user
USER appuser

# Make port 8080 available to the world outside this container
EXPOSE 8080

# Run main.py when the container launches, without letting the user set other params
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]