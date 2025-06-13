#!/usr/bin/env python3
"""
SQL Server Database Connection and Table Test Script
Tests connection to TestCompanyDB and performs basic operations
"""

import pyodbc
import pandas as pd
from datetime import datetime
import sys

# Database connection configuration
DB_CONFIG = {
    "server": "localhost,1433",
    "database": "TestCompanyDB", 
    "username": "sa",
    "password": "l.messi10",
    "driver": "{ODBC Driver 18 for SQL Server}",
    "trust_certificate": "yes"
}

def create_connection():
    """Create and return database connection"""
    try:
        # Build connection string
        conn_str = (
            f"DRIVER={DB_CONFIG['driver']};"
            f"SERVER={DB_CONFIG['server']};"
            f"DATABASE={DB_CONFIG['database']};"
            f"UID={DB_CONFIG['username']};"
            f"PWD={DB_CONFIG['password']};"
            f"TrustServerCertificate={DB_CONFIG['trust_certificate']};"
        )
        
        print("Connecting to SQL Server...")
        connection = pyodbc.connect(conn_str)
        print("✅ Successfully connected to SQL Server!")
        return connection
    
    except pyodbc.Error as e:
        print(f"❌ Error connecting to SQL Server: {e}")
        return None

def test_connection(conn):
    """Test basic connection and server info"""
    try:
        cursor = conn.cursor()
        
        # Test basic query
        cursor.execute("SELECT @@VERSION as ServerVersion")
        version = cursor.fetchone()[0]
        print(f"\n📋 Server Version: {version[:100]}...")
        
        # Get current database
        cursor.execute("SELECT DB_NAME() as CurrentDatabase")
        db_name = cursor.fetchone()[0]
        print(f"📋 Current Database: {db_name}")
        
        # Get current time
        cursor.execute("SELECT GETDATE() as CurrentTime")
        current_time = cursor.fetchone()[0]
        print(f"📋 Server Time: {current_time}")
        
        return True
    
    except Exception as e:
        print(f"❌ Connection test failed: {e}")
        return False

def list_tables(conn):
    """List all tables in the database"""
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT TABLE_NAME, TABLE_TYPE 
            FROM INFORMATION_SCHEMA.TABLES 
            WHERE TABLE_TYPE = 'BASE TABLE'
            ORDER BY TABLE_NAME
        """)
        
        tables = cursor.fetchall()
        print(f"\n📊 Tables in {DB_CONFIG['database']}:")
        print("-" * 40)
        for table in tables:
            print(f"  • {table[0]}")
        
        return [table[0] for table in tables]
    
    except Exception as e:
        print(f"❌ Error listing tables: {e}")
        return []

def get_table_info(conn, table_name):
    """Get detailed information about a specific table"""
    try:
        cursor = conn.cursor()
        
        # Get column information
        cursor.execute(f"""
            SELECT 
                COLUMN_NAME,
                DATA_TYPE,
                IS_NULLABLE,
                COLUMN_DEFAULT,
                CHARACTER_MAXIMUM_LENGTH
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_NAME = '{table_name}'
            ORDER BY ORDINAL_POSITION
        """)
        
        columns = cursor.fetchall()
        print(f"\n🔍 Table Structure: {table_name}")
        print("-" * 60)
        print(f"{'Column':<20} {'Type':<15} {'Nullable':<10} {'Default':<15}")
        print("-" * 60)
        
        for col in columns:
            col_name = col[0]
            data_type = col[1]
            if col[4]:  # Has max length
                data_type += f"({col[4]})"
            nullable = "YES" if col[2] == "YES" else "NO"
            default = str(col[3])[:12] if col[3] else "None"
            
            print(f"{col_name:<20} {data_type:<15} {nullable:<10} {default:<15}")
        
        # Get row count
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        row_count = cursor.fetchone()[0]
        print(f"\n📊 Total rows: {row_count}")
        
        return row_count
    
    except Exception as e:
        print(f"❌ Error getting table info for {table_name}: {e}")
        return 0

def test_table_data(conn, table_name, limit=5):
    """Display sample data from a table"""
    try:
        cursor = conn.cursor()
        cursor.execute(f"SELECT TOP {limit} * FROM {table_name}")
        
        # Get column names
        columns = [column[0] for column in cursor.description]
        rows = cursor.fetchall()
        
        print(f"\n📋 Sample data from {table_name} (first {limit} rows):")
        print("=" * 80)
        
        # Create DataFrame for better display
        df = pd.DataFrame.from_records(rows, columns=columns)
        print(df.to_string(index=False, max_cols=10, max_colwidth=15))
        
        return True
    
    except Exception as e:
        print(f"❌ Error reading data from {table_name}: {e}")
        return False

def test_complex_query(conn):
    """Test a complex query with joins"""
    try:
        cursor = conn.cursor()
        
        # Complex query: Employee project summary
        query = """
        SELECT 
            e.FirstName + ' ' + e.LastName AS EmployeeName,
            e.JobTitle,
            d.DepartmentName,
            COUNT(DISTINCT pa.ProjectID) AS ActiveProjects,
            SUM(pa.HoursWorked) AS TotalHours,
            AVG(p.Budget) AS AvgProjectBudget
        FROM Employees e
        LEFT JOIN Departments d ON e.DepartmentID = d.DepartmentID
        LEFT JOIN ProjectAssignments pa ON e.EmployeeID = pa.EmployeeID
        LEFT JOIN Projects p ON pa.ProjectID = p.ProjectID
        WHERE e.Status = 'Active'
        GROUP BY e.EmployeeID, e.FirstName, e.LastName, e.JobTitle, d.DepartmentName
        HAVING COUNT(DISTINCT pa.ProjectID) > 0
        ORDER BY TotalHours DESC
        """
        
        cursor.execute(query)
        rows = cursor.fetchall()
        columns = [column[0] for column in cursor.description]
        
        print(f"\n🔍 Complex Query Result: Employee Project Summary")
        print("=" * 100)
        
        df = pd.DataFrame.from_records(rows, columns=columns)
        print(df.to_string(index=False, float_format='%.2f'))
        
        return True
    
    except Exception as e:
        print(f"❌ Error executing complex query: {e}")
        return False

def test_insert_and_rollback(conn):
    """Test insert operation with rollback"""
    try:
        cursor = conn.cursor()
        
        # Start transaction
        print(f"\n🧪 Testing INSERT operation...")
        
        # Insert test employee
        insert_query = """
        INSERT INTO Employees (FirstName, LastName, Email, HireDate, JobTitle, Salary, DepartmentID, Status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
        
        test_data = (
            'Test', 'User', 'test.user@company.com', 
            datetime.now().date(), 'Test Engineer', 75000.00, 1, 'Active'
        )
        
        cursor.execute(insert_query, test_data)
        
        # Verify insert
        cursor.execute("SELECT COUNT(*) FROM Employees WHERE Email = 'test.user@company.com'")
        count = cursor.fetchone()[0]
        
        if count == 1:
            print("✅ Insert successful!")
            
            # Rollback the transaction
            conn.rollback()
            print("🔄 Transaction rolled back")
            
            # Verify rollback
            cursor.execute("SELECT COUNT(*) FROM Employees WHERE Email = 'test.user@company.com'")
            count_after = cursor.fetchone()[0]
            
            if count_after == 0:
                print("✅ Rollback successful - test data removed")
                return True
            else:
                print("❌ Rollback failed")
                return False
        else:
            print("❌ Insert failed")
            return False
    
    except Exception as e:
        print(f"❌ Error testing insert/rollback: {e}")
        conn.rollback()
        return False

def main():
    """Main function to run all tests"""
    print("🚀 SQL Server Database Test Script")
    print("=" * 50)
    
    # Create connection
    conn = create_connection()
    if not conn:
        print("❌ Cannot proceed without database connection")
        sys.exit(1)
    
    try:
        # Test connection
        if not test_connection(conn):
            return
        
        # List all tables
        tables = list_tables(conn)
        if not tables:
            print("❌ No tables found in database")
            return
        
        # Test each table
        for table in tables:
            get_table_info(conn, table)
            test_table_data(conn, table, limit=3)
            print("\n" + "="*80)
        
        # Test complex query
        test_complex_query(conn)
        
        # Test insert/rollback
        test_insert_and_rollback(conn)
        
        print(f"\n🎉 All tests completed successfully!")
        print(f"📊 Database: {DB_CONFIG['database']}")
        print(f"📊 Server: {DB_CONFIG['server']}")
        print(f"📊 Tables tested: {len(tables)}")
    
    except Exception as e:
        print(f"❌ Error during testing: {e}")
    
    finally:
        conn.close()
        print("\n🔌 Database connection closed")

if __name__ == "__main__":
    print("📋 Required packages: pyodbc, pandas")
    print("📋 Install with: pip install pyodbc pandas")
    print("\n" + "="*50)
    
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Script interrupted by user")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")