sudo docker run -e "ACCEPT_EULA=Y" \
    -e "MSSQL_SA_PASSWORD=l.messi10" \
    -p 1433:1433 \
    --name sqlserver2022 \
    --hostname sqlserver2022 \
    -d mcr.microsoft.com/mssql/server:2025-latest