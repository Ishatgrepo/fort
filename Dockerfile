# Use the official Python 3.10 slim image with Debian Buster as the base image
FROM python:3.10.4-slim-buster

# Update package list and install required dependencies
RUN apt-get update -y \
    && apt-get install -y git curl wget bash neofetch ffmpeg software-properties-common \
    && apt-get clean

# Install Python dependencies
COPY requirements.txt /requirements.txt
RUN pip3 install -U pip wheel \
    && pip3 install --no-cache-dir -U -r /requirements.txt

# Create and set the working directory inside the container
RUN mkdir /fwdbot
WORKDIR /fwdbot

# Copy the project files to the container
COPY . .

# Expose port for the Flask application
EXPOSE 8000
EXPOSE 8080

# Start Flask, Gunicorn, and the main Python script
CMD bash -c "flask run -h 0.0.0.0 -p 8000 & gunicorn app:app & python3 -m main"
