sudo docker cp create_test_db.sql sqlserver2022:/tmp/

sudo docker exec -it sqlserver2022 /opt/mssql-tools18/bin/sqlcmd \
    -S localhost -U sa -P "l.messi10"  -C -i /tmp/create_test_db.sql