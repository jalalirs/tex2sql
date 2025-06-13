import re
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, validator
import pyodbc
import logging

logger = logging.getLogger(__name__)

class ConnectionValidator:
    """Validate connection parameters"""
    
    @staticmethod
    def validate_server_address(server: str) -> bool:
        """Validate server address format"""
        if not server or len(server.strip()) == 0:
            return False
        
        # Basic validation - allow IP addresses, hostnames, and instances
        server = server.strip()
        
        # Check for valid characters (letters, numbers, dots, backslashes, commas for ports)
        if not re.match(r'^[a-zA-Z0-9._\\-]+(?:[:,]\d+)?$', server):
            return False
        
        return True
    
    @staticmethod
    def validate_database_name(database_name: str) -> bool:
        """Validate database name"""
        if not database_name or len(database_name.strip()) == 0:
            return False
        
        database_name = database_name.strip()
        
        # SQL Server database name rules
        if len(database_name) > 128:
            return False
        
        # Check for valid characters
        if not re.match(r'^[a-zA-Z0-9_][a-zA-Z0-9_.-]*$', database_name):
            return False
        
        return True
    
    @staticmethod
    def validate_table_name(table_name: str) -> bool:
        """Validate table name (with optional schema)"""
        if not table_name or len(table_name.strip()) == 0:
            return False
        
        table_name = table_name.strip()
        
        # Handle schema.table format
        parts = table_name.split('.')
        if len(parts) > 2:
            return False
        
        for part in parts:
            if not part or len(part) > 128:
                return False
            
            # Check for valid characters
            if not re.match(r'^[a-zA-Z0-9_][a-zA-Z0-9_-]*$', part):
                return False
        
        return True
    
    @staticmethod
    def validate_username(username: str) -> bool:
        """Validate username"""
        if not username or len(username.strip()) == 0:
            return False
        
        username = username.strip()
        
        # Basic length check
        if len(username) > 128:
            return False
        
        return True
    
    @staticmethod
    def validate_connection_name(name: str) -> bool:
        """Validate connection name"""
        if not name or len(name.strip()) == 0:
            return False
        
        name = name.strip()
        
        # Length check
        if len(name) > 255 or len(name) < 1:
            return False
        
        # Check for reasonable characters
        if not re.match(r'^[a-zA-Z0-9_\s.-]+$', name):
            return False
        
        return True
    
    @staticmethod
    def validate_driver(driver: str) -> bool:
        """Validate database driver name"""
        if not driver or len(driver.strip()) == 0:
            return False
        
        driver = driver.strip()
        
        # Common SQL Server drivers
        valid_drivers = [
            "ODBC Driver 18 for SQL Server",
            "ODBC Driver 17 for SQL Server",
            "ODBC Driver 13 for SQL Server",
            "ODBC Driver 11 for SQL Server",
            "SQL Server Native Client 11.0",
            "SQL Server Native Client 10.0",
            "SQL Server",
            "FreeTDS"
        ]
        
        # Check if it's a known valid driver
        if driver in valid_drivers:
            return True
        
        # Allow custom drivers that follow reasonable naming patterns
        # Should contain letters, numbers, spaces, dots, and common driver keywords
        if not re.match(r'^[a-zA-Z0-9\s.()_-]+$', driver):
            return False
        
        # Must contain some indication it's a driver
        driver_keywords = ['driver', 'client', 'odbc', 'native', 'sql', 'freetds']
        driver_lower = driver.lower()
        
        if any(keyword in driver_lower for keyword in driver_keywords):
            return True
        
        return False
    
    @staticmethod
    def get_available_drivers() -> List[str]:
        """Get list of available ODBC drivers on the system"""
        try:
            drivers = pyodbc.drivers()
            # Filter for SQL Server related drivers
            sql_drivers = [d for d in drivers if 'sql' in d.lower() or 'odbc' in d.lower()]
            return sql_drivers
        except Exception as e:
            logger.warning(f"Could not retrieve ODBC drivers: {e}")
            return []
    
    @staticmethod
    def is_driver_available(driver: str) -> bool:
        """Check if a specific driver is available on the system"""
        try:
            available_drivers = pyodbc.drivers()
            return driver in available_drivers
        except Exception as e:
            logger.warning(f"Could not check driver availability: {e}")
            return False
    
    @staticmethod
    def get_recommended_driver() -> Optional[str]:
        """Get the recommended driver based on what's available"""
        recommended_order = [
            "ODBC Driver 18 for SQL Server",
            "ODBC Driver 17 for SQL Server", 
            "ODBC Driver 13 for SQL Server",
            "ODBC Driver 11 for SQL Server",
            "SQL Server Native Client 11.0",
            "SQL Server Native Client 10.0"
        ]
        
        available_drivers = ConnectionValidator.get_available_drivers()
        
        for driver in recommended_order:
            if driver in available_drivers:
                return driver
        
        # Return the first available SQL Server driver
        sql_drivers = [d for d in available_drivers if 'sql' in d.lower()]
        if sql_drivers:
            return sql_drivers[0]
        
        return None

class SQLValidator:
    """Validate SQL queries"""
    
    @staticmethod
    def is_safe_query(sql: str) -> bool:
        """Check if SQL query is safe (read-only)"""
        sql_upper = sql.upper().strip()
        
        # Disallow dangerous keywords
        dangerous_keywords = [
            'DROP', 'DELETE', 'INSERT', 'UPDATE', 'CREATE', 'ALTER', 
            'TRUNCATE', 'EXEC', 'EXECUTE', 'SP_', 'XP_'
        ]
        
        for keyword in dangerous_keywords:
            if keyword in sql_upper:
                return False
        
        # Must start with SELECT
        if not sql_upper.startswith('SELECT'):
            return False
        
        return True
    
    @staticmethod
    def validate_sql_syntax(sql: str) -> Dict[str, Any]:
        """Basic SQL syntax validation"""
        try:
            sql = sql.strip()
            
            if not sql:
                return {"valid": False, "error": "Empty SQL query"}
            
            # Check for balanced parentheses
            if sql.count('(') != sql.count(')'):
                return {"valid": False, "error": "Unbalanced parentheses"}
            
            # Check for balanced quotes
            single_quotes = sql.count("'") - sql.count("\\'")
            if single_quotes % 2 != 0:
                return {"valid": False, "error": "Unbalanced single quotes"}
            
            # Basic keyword validation
            if not SQLValidator.is_safe_query(sql):
                return {"valid": False, "error": "Query contains unsafe operations"}
            
            return {"valid": True}
            
        except Exception as e:
            return {"valid": False, "error": str(e)}

class DataValidator:
    """Validate data formats and ranges"""
    
    @staticmethod
    def validate_column_description(column_name: str, description: str) -> Dict[str, Any]:
        """Validate column description entry"""
        errors = []
        
        # Validate column name
        if not column_name or len(column_name.strip()) == 0:
            errors.append("Column name is required")
        elif len(column_name.strip()) > 128:
            errors.append("Column name too long (max 128 characters)")
        elif not re.match(r'^[a-zA-Z0-9_][a-zA-Z0-9_\s.-]*$', column_name.strip()):
            errors.append("Column name contains invalid characters")
        
        # Validate description
        if description and len(description) > 1000:
            errors.append("Description too long (max 1000 characters)")
        
        return {
            "valid": len(errors) == 0,
            "errors": errors
        }
    
    @staticmethod
    def validate_progress_value(progress: int) -> bool:
        """Validate progress percentage"""
        return 0 <= progress <= 100
    
    @staticmethod
    def sanitize_string(value: str) -> str:
        """Sanitize string input"""
        if not value:
            return ""
        
        # Remove null bytes and control characters
        sanitized = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x84\x86-\x9f]', '', value)
        
        # Limit length
        return sanitized[:1000]

def validate_connection_data(connection_data) -> List[str]:
    """Comprehensive connection data validation"""
    errors = []
    
    if not ConnectionValidator.validate_connection_name(connection_data.name):
        errors.append("Invalid connection name")
    
    if not ConnectionValidator.validate_server_address(connection_data.server):
        errors.append("Invalid server address")
    
    if not ConnectionValidator.validate_database_name(connection_data.database_name):
        errors.append("Invalid database name")
    
    if not ConnectionValidator.validate_username(connection_data.username):
        errors.append("Invalid username")
    
    if not ConnectionValidator.validate_table_name(connection_data.table_name):
        errors.append("Invalid table name")
    
    if not connection_data.password or len(connection_data.password.strip()) == 0:
        errors.append("Password is required")
    
    # Validate driver (optional)
    if hasattr(connection_data, 'driver') and connection_data.driver:
        # Only validate if driver is provided and not empty
        if connection_data.driver.strip():  # Check if not just whitespace
            if not ConnectionValidator.validate_driver(connection_data.driver):
                errors.append("Invalid driver name")
            elif not ConnectionValidator.is_driver_available(connection_data.driver):
                errors.append(f"Driver '{connection_data.driver}' is not available on this system")
    
    return errors

def get_driver_validation_info(driver: str = None) -> Dict[str, Any]:
    """Get comprehensive driver validation information"""
    available_drivers = ConnectionValidator.get_available_drivers()
    recommended_driver = ConnectionValidator.get_recommended_driver()
    
    result = {
        "available_drivers": available_drivers,
        "recommended_driver": recommended_driver,
        "driver_count": len(available_drivers),
        "driver_optional": True  # Indicate that driver is optional
    }
    
    if driver and driver.strip():  # Only validate if driver is provided and not empty
        result.update({
            "provided_driver": driver,
            "is_valid": ConnectionValidator.validate_driver(driver),
            "is_available": ConnectionValidator.is_driver_available(driver)
        })
    else:
        result.update({
            "provided_driver": None,
            "will_use_default": True,
            "note": "No driver specified, system will use default available driver"
        })
    
    return result