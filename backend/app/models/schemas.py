from pydantic import BaseModel, Field, EmailStr, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
import uuid


# ========================
# CORE ENUMS
# ========================

class ConnectionStatus(str, Enum):
    TESTING = "testing"
    TEST_SUCCESS = "test_success"
    TEST_FAILED = "test_failed"
    GENERATING_DATA = "generating_data"
    DATA_GENERATED = "data_generated"
    TRAINING = "training"
    TRAINED = "trained"
    TRAINING_FAILED = "training_failed"

class TaskType(str, Enum):
    TEST_CONNECTION = "test_connection"
    GENERATE_DATA = "generate_data"
    TRAIN_MODEL = "train_model"
    QUERY = "query"

class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

class UserRole(str, Enum):
    USER = "user"
    ADMIN = "admin"
    SUPER_ADMIN = "super_admin"

class MessageType(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"



# ========================
# USER MANAGEMENT SCHEMAS
# ========================

class UserCreate(BaseModel):
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=30, pattern="^[a-zA-Z0-9_-]+$")
    full_name: Optional[str] = Field(None, max_length=255)
    password: str = Field(..., min_length=8, max_length=128)
    company: Optional[str] = Field(None, max_length=255)
    job_title: Optional[str] = Field(None, max_length=255)

    @validator('password')
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        if not any(c.isupper() for c in v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not any(c.islower() for c in v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not any(c.isdigit() for c in v):
            raise ValueError('Password must contain at least one digit')
        return v

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    id: str
    email: str
    username: str
    full_name: Optional[str] = None
    role: UserRole
    is_active: bool
    is_verified: bool
    profile_picture_url: Optional[str] = None
    bio: Optional[str] = None
    company: Optional[str] = None
    job_title: Optional[str] = None
    created_at: datetime
    last_login_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class UserUpdate(BaseModel):
    full_name: Optional[str] = Field(None, max_length=255)
    bio: Optional[str] = Field(None, max_length=1000)
    company: Optional[str] = Field(None, max_length=255)
    job_title: Optional[str] = Field(None, max_length=255)
    profile_picture_url: Optional[str] = Field(None, max_length=500)

class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8, max_length=128)

    @validator('new_password')
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        if not any(c.isupper() for c in v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not any(c.islower() for c in v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not any(c.isdigit() for c in v):
            raise ValueError('Password must contain at least one digit')
        return v

class PasswordReset(BaseModel):
    email: EmailStr

class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str = Field(..., min_length=8, max_length=128)

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse

class TokenRefresh(BaseModel):
    refresh_token: str

class EmailVerification(BaseModel):
    token: str


# ========================
# CONNECTION SCHEMAS
# ========================

class ConnectionCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="Connection name (unique per user)")
    server: str = Field(..., min_length=1, description="Database server address")
    database_name: str = Field(..., min_length=1, description="Database name")
    username: str = Field(..., min_length=1, description="Database username")
    password: str = Field(..., min_length=1, description="Database password")
    table_name: str = Field(..., min_length=1, description="Full table name (schema.table)")
    driver: Optional[str] = Field(None, description="Database driver")

class ConnectionTestRequest(BaseModel):
    connection_data: ConnectionCreate

class ConnectionTestResult(BaseModel):
    success: bool
    error_message: Optional[str] = None
    sample_data: Optional[List[Dict[str, Any]]] = None
    column_info: Optional[Dict[str, Any]] = None
    task_id: str

class ConnectionResponse(BaseModel):
    id: str
    name: str
    server: str
    database_name: str
    table_name: str
    driver: Optional[str] = None
    status: ConnectionStatus
    test_successful: bool
    column_descriptions_uploaded: bool
    generated_examples_count: int
    total_queries: int = 0
    last_queried_at: Optional[datetime] = None
    created_at: datetime
    trained_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class ConnectionListResponse(BaseModel):
    connections: List[ConnectionResponse]
    total: int

class ConnectionDeleteResponse(BaseModel):
    success: bool
    message: str

# Add these schemas to app/models/schemas.py

class SchemaRefreshResponse(BaseModel):
    """Response for schema refresh operation"""
    task_id: str
    connection_id: str
    status: str
    stream_url: str
    message: str = "Schema refresh started"

class ConnectionSchemaResponse(BaseModel):
    """Response for connection schema"""
    connection_id: str
    connection_name: str
    schema: Dict[str, Any]
    last_refreshed: Optional[str]
    total_columns: int

class ColumnInfo(BaseModel):
    """Column information with all details"""
    column_name: str
    data_type: str
    variable_range: str = ""
    description: str = ""
    has_description: bool = False
    categories: Optional[List[str]] = None
    range: Optional[Dict[str, float]] = None
    date_range: Optional[Dict[str, str]] = None

class ColumnDescriptionsResponse(BaseModel):
    """Response for column descriptions"""
    connection_id: str
    connection_name: str
    column_descriptions: List[ColumnInfo]
    total_columns: int
    has_descriptions: bool

class UpdateColumnDescriptionsResponse(BaseModel):
    """Response for updating column descriptions"""
    success: bool
    message: str
    connection_id: str
    total_columns: int



# ========================
# CONVERSATION & MESSAGE SCHEMAS
# ========================



class ConversationQueryRequest(BaseModel):
    question: str
    conversation_id: Optional[str] = None  # If provided, add to existing conversation

class ConversationQueryResponse(BaseModel):
    session_id: str  # For SSE streaming
    conversation_id: str
    user_message_id: str  # The user message just created
    stream_url: str
    is_new_conversation: bool
    connection_locked: bool  # True if connection just got locked

# UI Response Types - These are sent via SSE to the frontend
class SQLResponse(BaseModel):
    sql: str
    is_valid: bool
    error_message: Optional[str] = None

class DataResponse(BaseModel):
    data: List[Dict[str, Any]]
    row_count: int
    column_info: Optional[Dict[str, Any]] = None
    execution_time: Optional[int] = None  # milliseconds

class PlotResponse(BaseModel):
    chart_data: Dict[str, Any]  # Plotly figure JSON
    chart_code: Optional[str] = None  # Generated Python code
    should_generate: bool = True
    error_message: Optional[str] = None

class SummaryResponse(BaseModel):
    summary: str
    key_insights: Optional[List[str]] = None
    followup_questions: Optional[List[str]] = None

# Complete query result (stored in assistant message)
class QueryResult(BaseModel):
    question: str
    sql_response: Optional[SQLResponse] = None
    data_response: Optional[DataResponse] = None
    plot_response: Optional[PlotResponse] = None
    summary_response: Optional[SummaryResponse] = None
    error_message: Optional[str] = None
    processing_time: Optional[int] = None  # Total processing time in ms

class MessageResponse(BaseModel):
    id: str
    content: str
    message_type: MessageType
    
    # Query result data (for assistant messages)
    generated_sql: Optional[str] = None
    query_results: Optional[Dict[str, Any]] = None  # DataResponse
    chart_data: Optional[Dict[str, Any]] = None     # PlotResponse
    summary: Optional[str] = None                   # SummaryResponse.summary
    
    # Metadata
    execution_time: Optional[int] = None
    row_count: Optional[int] = None
    tokens_used: Optional[int] = None
    model_used: Optional[str] = None
    is_edited: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class MessageCreate(BaseModel):
    conversation_id: str
    content: str
    message_type: MessageType = MessageType.USER
    generated_sql: Optional[str] = None
    query_results: Optional[Dict[str, Any]] = None
    chart_data: Optional[Dict[str, Any]] = None
    summary: Optional[str] = None
    execution_time: Optional[int] = None
    row_count: Optional[int] = None
    tokens_used: Optional[int] = None
    model_used: Optional[str] = None

class ConversationCreate(BaseModel):
    connection_id: str
    title: Optional[str] = None  # Auto-generated if not provided
    description: Optional[str] = None

class ConversationUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=500)
    description: Optional[str] = Field(None, max_length=2000)
    connection_id: Optional[str] = None  # Can only change if connection_locked=False
    is_pinned: Optional[bool] = None

class ConversationResponse(BaseModel):
    id: str
    connection_id: str
    connection_name: str
    title: str
    description: Optional[str] = None
    is_active: bool
    is_pinned: bool
    connection_locked: bool  # Whether connection can be changed
    message_count: int
    total_queries: int
    created_at: datetime
    updated_at: datetime
    last_message_at: datetime
    latest_message: Optional[str] = None

    class Config:
        from_attributes = True

class ConversationWithMessagesResponse(BaseModel):
    id: str
    connection_id: str
    connection_name: str
    title: str
    description: Optional[str] = None
    is_active: bool
    is_pinned: bool
    connection_locked: bool
    message_count: int
    total_queries: int
    created_at: datetime
    updated_at: datetime
    last_message_at: datetime
    messages: List[MessageResponse]

    class Config:
        from_attributes = True

class ConversationListResponse(BaseModel):
    conversations: List[ConversationResponse]
    total: int
    page: int = 1
    per_page: int = 20
    total_pages: int

class SuggestedQuestionsResponse(BaseModel):
    questions: List[str]
    connection_id: str
    conversation_id: Optional[str] = None
    total: int


# ========================
# TRAINING SCHEMAS
# ========================

class ColumnDescriptionItem(BaseModel):
    column_name: str
    data_type: Optional[str] = None
    variable_range: Optional[str] = None
    description: Optional[str] = None

class TrainingDataView(BaseModel):
    connection_id: str
    connection_name: str
    initial_prompt: str
    column_descriptions: List[ColumnDescriptionItem]
    generated_examples: List[Dict[str, str]] = []
    total_examples: int = 0

class GenerateExamplesRequest(BaseModel):
    connection_id: str = Field(..., description="Connection UUID")
    num_examples: int = Field(default=20, ge=1, le=100, description="Number of examples to generate")

class TrainingExampleResponse(BaseModel):
    id: str
    question: str
    sql: str
    generated_at: datetime

    class Config:
        from_attributes = True

class ConnectionAddRequest(BaseModel):
    connection_data: ConnectionCreate
    column_descriptions: Optional[List[ColumnDescriptionItem]] = None
    generate_examples: bool = True
    num_examples: int = Field(default=20, ge=1, le=100)

class TrainModelRequest(BaseModel):
    connection_id: str = Field(..., description="Connection UUID to train")


# ========================
# TASK SCHEMAS
# ========================

class TaskResponse(BaseModel):
    task_id: str
    connection_id: Optional[str] = None
    task_type: TaskType
    status: TaskStatus
    progress: int
    stream_url: str
    created_at: datetime


    class Config:
        from_attributes = True

class TaskStatusResponse(BaseModel):
    task_id: str
    status: TaskStatus
    progress: int
    error_message: Optional[str] = None
    completed_at: Optional[datetime] = None


# ========================
# ANALYTICS SCHEMAS
# ========================

class UserStatsResponse(BaseModel):
    user_id: str
    total_connections: int
    total_conversations: int
    total_messages: int
    total_queries: int
    active_conversations: int
    last_activity: Optional[datetime] = None

class ConversationStatsResponse(BaseModel):
    total_conversations: int
    active_conversations: int
    pinned_conversations: int
    total_messages: int
    total_queries: int
    avg_messages_per_conversation: float


# ========================
# UTILITY SCHEMAS
# ========================

class ColumnDescriptionUpload(BaseModel):
    column: str
    description: str

class ErrorResponse(BaseModel):
    detail: str
    error_code: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class ValidationErrorResponse(BaseModel):
    detail: List[Dict[str, Any]]
    error_code: str = "validation_error"
    timestamp: datetime = Field(default_factory=datetime.utcnow)