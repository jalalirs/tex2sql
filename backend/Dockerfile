# First stage: Install MSSQL ODBC driver
FROM debian:11-slim as odbc-installer

RUN apt-get update && apt-get install -y \
    curl \
    gnupg2 \
    apt-transport-https \
    ca-certificates \
    unixodbc \
    unixodbc-dev

# Install MSSQL ODBC driver
RUN curl -fsSL https://packages.microsoft.com/keys/microsoft.asc | apt-key add - && \
    curl -fsSL https://packages.microsoft.com/config/debian/11/prod.list > /etc/apt/sources.list.d/mssql-release.list && \
    apt-get update && \
    ACCEPT_EULA=Y apt-get install -y msodbcsql18

# Second stage: Python application
FROM python:3.11-slim

WORKDIR /app

# Install basic dependencies
RUN apt-get update && apt-get install -y \
    unixodbc \
    unixodbc-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy ODBC driver from first stage
COPY --from=odbc-installer /opt/microsoft/msodbcsql18 /opt/microsoft/msodbcsql18
COPY --from=odbc-installer /etc/odbcinst.ini /etc/odbcinst.ini

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