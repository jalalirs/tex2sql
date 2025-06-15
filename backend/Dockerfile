# Use a slim Python 3.11 image, which is based on Debian Bookworm (12)
FROM python:3.11-slim
WORKDIR /app

# Install initial system dependencies required for both drivers and general operation.
# This includes `unixodbc` and `unixodbc-dev`, which will be updated by the Microsoft drivers.
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        curl \
        gnupg2 \
        apt-transport-https \
        ca-certificates \
        unixodbc \
        unixodbc-dev && \
    rm -rf /var/lib/apt/lists/*

# --- Install ODBC Driver 17 for SQL Server (msodbcsql17) ---
# ODBC Driver 17 is typically packaged for older Debian releases (e.g., Debian 10 "Buster").
# We add its specific repository to install it.
RUN echo "deb [arch=amd64,trusted=yes] https://packages.microsoft.com/debian/10/prod buster main" > /etc/apt/sources.list.d/mssql-release-17.list && \
    curl https://packages.microsoft.com/keys/microsoft.asc | tee /etc/apt/trusted.gpg.d/microsoft.asc && \
    apt-get update && \
    # ACCEPT_EULA is required for Microsoft packages.
    ACCEPT_EULA=Y apt-get install -y msodbcsql17 && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# --- Install ODBC Driver 18 for SQL Server (msodbcsql18) ---
# ODBC Driver 18 is packaged for newer Debian releases (e.g., Debian 11 "Bullseye").
# Installing this will likely upgrade shared ODBC components (like libodbc1) to newer versions.
RUN echo "deb [arch=amd64,trusted=yes] https://packages.microsoft.com/debian/11/prod bullseye main" > /etc/apt/sources.list.d/mssql-release-18.list && \
    # The Microsoft GPG key should already be present from the previous step.
    apt-get update && \
    ACCEPT_EULA=Y apt-get install -y msodbcsql18 && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Clean up apt lists and temporary key files after installation to reduce image size.
RUN rm -f /etc/apt/sources.list.d/mssql-release-17.list \
           /etc/apt/sources.list.d/mssql-release-18.list \
           /etc/apt/trusted.gpg.d/microsoft.asc

# Copy Python requirements file and install dependencies.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code into the image.
COPY . .

# Create necessary directories for your application.
RUN mkdir -p /app/data /app/uploads

# Expose the port your application will listen on.
EXPOSE 6020

# Command to run your application when the container starts.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "6020"]
