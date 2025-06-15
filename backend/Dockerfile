FROM python:3.11-slim
WORKDIR /app

# Install initial system dependencies, but specifically remove unixodbc and unixodbc-dev if they conflict
# We will rely on the Microsoft repository to provide compatible versions if needed.
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        curl \
        gnupg2 \
        apt-transport-https \
        ca-certificates && \
    # Remove potentially conflicting unixodbc packages if they were pre-installed
    apt-get remove -y --purge unixodbc unixodbc-dev libodbc2 libodbcinst2 && \
    rm -rf /var/lib/apt/lists/*

# Install ODBC Driver 18 using Microsoft's script
# This script will install msodbcsql18 and its required dependencies,
# including compatible unixodbc components.
RUN curl https://packages.microsoft.com/config/debian/11/prod.list > /etc/apt/sources.list.d/mssql-release.list && \
    curl https://packages.microsoft.com/keys/microsoft.asc | tee /etc/apt/trusted.gpg.d/microsoft.asc && \
    apt-get update && \
    ACCEPT_EULA=Y apt-get install -y msodbcsql18 && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create data and uploads directories
RUN mkdir -p /app/data /app/uploads

# Expose port
EXPOSE 6020

# Run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "6020"]