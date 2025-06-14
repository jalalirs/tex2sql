export interface Connection {
    id: string;
    name: string;
    server: string;
    database_name: string;
    table_name: string;
    driver?: string;
    status: 'testing' | 'test_success' | 'test_failed' | 'generating_data' | 'data_generated' | 'training' | 'trained' | 'training_failed';
    test_successful: boolean;
    column_descriptions_uploaded: boolean;
    generated_examples_count: number;
    total_queries: number;
    last_queried_at?: string;
    created_at: string;
    trained_at?: string;
  }
  
  export interface Conversation {
    id: string;
    connection_id: string;
    connection_name: string;
    title: string;
    description?: string;
    is_active: boolean;
    is_pinned: boolean;
    connection_locked: boolean;
    message_count: number;
    total_queries: number;
    created_at: string;
    updated_at: string;
    last_message_at: string;
    latest_message?: string;
  }
  
  export interface Message {
    id: string;
    content: string;
    message_type: 'user' | 'assistant' | 'system';
    generated_sql?: string;
    query_results?: {
      data: any[];
      row_count: number;
    };
    chart_data?: {
      type: string;
      title: string;
      data: number[];
      labels: string[];
    };
    summary?: string;
    execution_time?: number;
    row_count?: number;
    tokens_used?: number;
    model_used?: string;
    is_edited: boolean;
    created_at: string;
    updated_at: string;
  }