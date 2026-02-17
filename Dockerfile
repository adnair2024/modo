# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY . /app

# Install system dependencies needed for building certain Python packages
RUN apt-get update && apt-get install -y \
    gcc \
    python3-dev \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install any needed packages specified in requirements.txt
# We use --no-cache-dir to keep the image small
RUN pip install --no-cache-dir -r requirements.txt

# Make port 8000 available to the world outside this container
EXPOSE 8000

# Define environment variable
ENV FLASK_APP=app.py

# Run database migrations and then start the server
# Note: In production with multiple replicas, migrations should ideally be a separate job.
# For a single instance/simple setup, running it here is acceptable but 'CMD' is overridden by Northflank if specified there.
# We'll use a shell script entrypoint to ensure migrations run.
COPY docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

ENTRYPOINT ["docker-entrypoint.sh"]
