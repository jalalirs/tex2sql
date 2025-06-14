from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from enum import Enum
from datetime import datetime
import uuid

class VannaConfig(BaseModel):
    """Configuration for Vanna instance"""
    api_key: str
    base_url: str = "https://api.openai.com/v1"
    model: str = "gpt-4"
    max_tokens: int = 4000
    temperature: float = 0.1
    
class DatabaseConfig(BaseModel):
    """Database connection configuration for Vanna"""
    server: str
    database_name: str
    username: str
    password: str
    table_name: str
    driver: Optional[str] = Field(
        default="ODBC Driver 17 for SQL Server",
        description="Database driver name"
    )
    
    def to_odbc_connection_string(self) -> str:
        """Convert to ODBC connection string for SQL Server"""
        # Use the driver field, fallback to default if None/empty
        driver_name = self.driver if self.driver and self.driver.strip() else "ODBC Driver 17 for SQL Server"
        
        return (
            f"DRIVER={{{driver_name}}};"
            f"SERVER={self.server};"
            f"DATABASE={self.database_name};"
            f"UID={self.username};"
            f"PWD={self.password};"
            f"TrustServerCertificate=yes;"
        )

class ColumnInfo(BaseModel):
    """Column information from database schema analysis"""
    column_name: str
    data_type: str
    categories: Optional[List[str]] = None  # For categorical columns
    range: Optional[Dict[str, float]] = None  # For numerical columns: {"min": x, "max": y, "avg": z}
    date_range: Optional[Dict[str, str]] = None  # For date columns: {"min": "date", "max": "date"}
    
class TrainingDocumentation(BaseModel):
    """Documentation entry for Vanna training"""
    doc_type: str  # e.g., "mssql_conventions", "table_info", "column_details"
    content: str

class TrainingExample(BaseModel):
    """Training example (question-SQL pair)"""
    question: str
    sql: str

class VannaTrainingData(BaseModel):
    """Complete training data structure"""
    documentation: List[TrainingDocumentation]
    examples: List[TrainingExample]
    column_descriptions: Optional[List[Dict[str, str]]] = None  # From uploaded CSV
    # NEW: User context for training data
    user_id: Optional[str] = None
    user_email: Optional[str] = None
    generated_at: Optional[datetime] = None

class QueryRequest(BaseModel):
    """Request for SQL generation from natural language"""
    question: str
    connection_id: str
    allow_llm_to_see_data: bool = True
    chat_history: Optional[List[Dict[str, str]]] = None
    # NEW: User context for queries
    user_id: Optional[str] = None
    session_id: Optional[str] = None

class QueryResponse(BaseModel):
    """Complete response for a query"""
    question: str
    sql: Optional[str] = None
    is_sql_valid: bool = False
    data: Optional[List[Dict[str, Any]]] = None
    chart_code: Optional[str] = None
    chart_data: Optional[Dict[str, Any]] = None  # Plotly figure JSON
    summary: Optional[str] = None
    followup_questions: Optional[List[str]] = None
    error_message: Optional[str] = None
    # NEW: Response metadata
    execution_time: Optional[float] = None
    row_count: Optional[int] = None
    user_id: Optional[str] = None
    connection_id: Optional[str] = None

class SuggestedQuestionsResponse(BaseModel):
    """Response for suggested questions"""
    questions: List[str]
    connection_id: str
    conversation_id: Optional[str] = None
    total: int = Field(default=0)
    # NEW: User context
    user_id: Optional[str] = None

# Vanna Operation Types for logging and tracking
class VannaOperationType(str, Enum):
    SETUP = "setup"
    TRAIN_DOCUMENTATION = "train_documentation"
    TRAIN_EXAMPLE = "train_example"
    GENERATE_SQL = "generate_sql"
    VALIDATE_SQL = "validate_sql"
    EXECUTE_SQL = "execute_sql"
    GENERATE_CHART = "generate_chart"
    GENERATE_SUMMARY = "generate_summary"
    GENERATE_FOLLOWUP = "generate_followup"
    GENERATE_QUESTIONS = "generate_questions"
    # NEW: Additional operations
    USER_ACCESS_VALIDATION = "user_access_validation"
    MODEL_CLEANUP = "model_cleanup"

class VannaOperation(BaseModel):
    """Tracking model for Vanna operations"""
    operation_type: VannaOperationType
    connection_id: str
    input_data: Optional[Dict[str, Any]] = None
    output_data: Optional[Dict[str, Any]] = None
    success: bool
    error_message: Optional[str] = None
    execution_time: Optional[float] = None  # In seconds
    # NEW: User context and tracking
    user_id: Optional[str] = None
    user_email: Optional[str] = None
    session_id: Optional[str] = None
    operation_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = Field(default_factory=datetime.utcnow)

# Data Generation Models
class DataGenerationConfig(BaseModel):
    """Configuration for LLM-based data generation"""
    num_examples: int = Field(default=20, ge=1, le=100)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_retries: int = Field(default=3, ge=1, le=10)
    # NEW: User context
    user_id: Optional[str] = None
    
class DataGenerationProgress(BaseModel):
    """Progress tracking for data generation"""
    connection_id: str
    total_examples: int
    completed_examples: int
    failed_examples: int
    current_example: Optional[TrainingExample] = None
    progress_percentage: int
    # NEW: User and session context
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    
class ColumnDescriptionEntry(BaseModel):
    """Single column description entry"""
    column: str
    description: str
    
class GeneratedDataResult(BaseModel):
    """Result of data generation process"""
    success: bool
    total_generated: int
    failed_count: int
    examples: List[TrainingExample]
    documentation: List[TrainingDocumentation]
    generation_time: float
    error_message: Optional[str] = None
    # NEW: Enhanced metadata
    connection_id: Optional[str] = None
    user_id: Optional[str] = None
    user_email: Optional[str] = None
    generated_at: Optional[datetime] = None

# Training Models
class TrainingConfig(BaseModel):
    """Configuration for Vanna model training"""
    connection_id: str
    retrain: bool = True  # Always retrain for new connections
    clear_existing: bool = True
    # NEW: User context
    user_id: Optional[str] = None
    user_email: Optional[str] = None
    
class TrainingProgress(BaseModel):
    """Progress tracking for model training"""
    connection_id: str
    total_steps: int
    completed_steps: int
    current_step: str
    progress_percentage: int
    # NEW: User and session context
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    
class TrainingResult(BaseModel):
    """Result of training process"""
    success: bool
    connection_id: str
    training_time: float
    documentation_count: int
    examples_count: int
    error_message: Optional[str] = None
    # NEW: Enhanced metadata
    user_id: Optional[str] = None
    user_email: Optional[str] = None
    trained_at: Optional[datetime] = None

# Chart Generation Models
class ChartRequest(BaseModel):
    """Request for chart generation"""
    question: str
    sql: str
    data: List[Dict[str, Any]]
    # NEW: User context
    user_id: Optional[str] = None
    connection_id: Optional[str] = None
    
class ChartResponse(BaseModel):
    """Response for chart generation"""
    should_generate: bool
    chart_code: Optional[str] = None
    chart_figure: Optional[Dict[str, Any]] = None  # Plotly figure as JSON
    error_message: Optional[str] = None
    # NEW: Metadata
    generation_time: Optional[float] = None
    chart_type: Optional[str] = None  # e.g., "bar", "line", "pie"

# NEW: User Access Models
class UserAccessRequest(BaseModel):
    """Request to validate user access to Vanna resources"""
    user_id: str
    connection_id: str
    operation_type: VannaOperationType
    
class UserAccessResponse(BaseModel):
    """Response for user access validation"""
    has_access: bool
    user_id: str
    connection_id: str
    reason: Optional[str] = None  # Reason for denial
    validated_at: datetime = Field(default_factory=datetime.utcnow)

# NEW: Enhanced Analytics Models
class VannaUsageMetrics(BaseModel):
    """Usage metrics for Vanna operations"""
    user_id: str
    connection_id: str
    operation_counts: Dict[VannaOperationType, int] = Field(default_factory=dict)
    total_operations: int = 0
    average_execution_time: Optional[float] = None
    success_rate: Optional[float] = None
    last_activity: Optional[datetime] = None
    
class ConnectionTrainingMetrics(BaseModel):
    """Training metrics for a connection"""
    connection_id: str
    user_id: str
    documentation_entries: int = 0
    training_examples: int = 0
    model_size: Optional[int] = None  # Size of ChromaDB
    last_trained: Optional[datetime] = None
    training_duration: Optional[float] = None
    retrain_count: int = 0

# MS SQL Server specific constants and templates
class MSSQLConstants:
    """Constants for MS SQL Server specific operations"""
    
    DRIVER_STRING = "ODBC Driver 17 for SQL Server"
    
    # MS SQL Server conventions documentation
    MSSQL_CONVENTIONS_DOC = """When generating SQL queries for Microsoft SQL Server, always adhere to the following specific syntax and conventions. Unlike other SQL dialects, MS SQL Server uses square brackets [] to delimit identifiers (like table or column names), especially if they are SQL keywords (e.g., [View]) or contain spaces. For limiting the number of rows returned, always use the TOP N clause immediately after the SELECT keyword, ensuring there is a space between TOP and the numerical value (e.g., SELECT TOP 5 Company_Name). The LIMIT and OFFSET keywords, commonly found in MySQL or PostgreSQL, are not standard. For string concatenation, use the + operator. Date and time manipulation often relies on functions like GETDATE(), DATEADD(), DATEDIFF(), and CONVERT(). Handle NULL values using IS NULL, IS NOT NULL, or functions like ISNULL(expression, replacement) and COALESCE(expression1, expression2, ...). While often case-insensitive by default depending on collation, it's best practice to match casing with database objects. Complex queries frequently leverage Common Table Expressions (CTEs) defined with WITH for readability and structuring multi-step logic. Pay close attention to correct spacing and keyword usage to avoid syntax errors."""
    
    # SQL keywords that need brackets
    SQL_KEYWORDS = {
        'view', 'table', 'index', 'key', 'order', 'group', 'having', 
        'where', 'select', 'from', 'join', 'union', 'case', 'when', 
        'then', 'else', 'end', 'as', 'distinct', 'top', 'percent'
    }
    
    @classmethod
    def should_bracket_identifier(cls, identifier: str) -> bool:
        """Check if an identifier should be wrapped in brackets"""
        return (
            identifier.lower() in cls.SQL_KEYWORDS or
            ' ' in identifier or
            '-' in identifier or
            identifier.startswith(tuple('0123456789'))
        )

# Validation Models
class VannaInstanceValidation(BaseModel):
    """Validation result for Vanna instance"""
    is_valid: bool
    connection_successful: bool
    chromadb_accessible: bool
    llm_accessible: bool
    error_messages: List[str] = []
    # NEW: User context and validation details
    user_id: Optional[str] = None
    connection_id: Optional[str] = None
    validated_at: datetime = Field(default_factory=datetime.utcnow)
    validation_duration: Optional[float] = None

# NEW: Error Handling Models
class VannaError(BaseModel):
    """Standardized error model for Vanna operations"""
    error_type: str  # e.g., "connection_error", "sql_error", "access_denied"
    error_message: str
    operation_type: VannaOperationType
    connection_id: Optional[str] = None
    user_id: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    error_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    
class VannaErrorResponse(BaseModel):
    """Error response for API calls"""
    success: bool = False
    error: VannaError
    suggestion: Optional[str] = None  # Suggested action for user

# NEW: Batch Operations Models
class BatchTrainingRequest(BaseModel):
    """Request for batch training operations"""
    connection_ids: List[str]
    user_id: str
    force_retrain: bool = False
    
class BatchTrainingResponse(BaseModel):
    """Response for batch training operations"""
    total_connections: int
    successful_trainings: int
    failed_trainings: int
    results: List[TrainingResult]
    batch_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    started_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None