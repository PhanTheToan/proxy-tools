FROM python:3.11-alpine

# Set working directory
WORKDIR /app

# Copy the backend code
COPY backend/ /app/backend/

# Switch to backend directory
WORKDIR /app/backend

# Environment variables to trigger Docker-specific logic in server.py
ENV HOST=0.0.0.0
ENV DOCKER_ENV=true

# Expose UI Port
EXPOSE 8085

# Expose 3000 ports for auto-discovery proxies
EXPOSE 8100-11100

# Start the application
CMD ["python", "server.py"]
