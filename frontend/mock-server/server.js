const jsonServer = require('json-server');
const path = require('path');
const { Connection, Request, TYPES } = require('tedious');

const server = jsonServer.create();
const router = jsonServer.router(path.join(__dirname, 'db.json'));
const middlewares = jsonServer.defaults();

server.use(middlewares);
server.use(jsonServer.bodyParser);

// Mock storage for schemas, column descriptions, and training data
const mockSchemas = new Map();
const mockColumnDescriptions = new Map();
const mockTrainingData = new Map();

// Helper function to test MSSQL connection
function testSQLConnection(connectionData) {
  return new Promise((resolve, reject) => {
    const config = {
      server: connectionData.server.split(',')[0], // Remove port if included
      options: {
        port: connectionData.server.includes(',') ? parseInt(connectionData.server.split(',')[1]) : 1433,
        database: connectionData.database_name,
        encrypt: false, // Set to true if using Azure
        trustServerCertificate: true // For development
      },
      authentication: {
        type: 'default',
        options: {
          userName: connectionData.username || 'sa',
          password: connectionData.password || 'l.messi10'
        }
      }
    };

    const connection = new Connection(config);

    let testResult = {
      success: false,
      error: null,
      sampleData: [],
      columnInfo: {}
    };

    connection.connect((err) => {
      if (err) {
        testResult.error = `Connection failed: ${err.message}`;
        return resolve(testResult);
      }

      console.log('Connected to MSSQL database');

      // First, get sample data
      const sampleQuery = `SELECT TOP 10 * FROM ${connectionData.table_name}`;
      const sampleRequest = new Request(sampleQuery, (err) => {
        if (err) {
          testResult.error = `Query failed: ${err.message}`;
          connection.close();
          return resolve(testResult);
        }
      });

      let sampleRows = [];
      let columns = [];

      sampleRequest.on('columnMetadata', (columnMetadata) => {
        columns = columnMetadata.map(col => ({
          name: col.colName,
          type: col.type.name
        }));
      });

      sampleRequest.on('row', (row) => {
        const rowData = {};
        row.forEach((column, index) => {
          rowData[columns[index].name] = column.value;
        });
        sampleRows.push(rowData);
      });

      sampleRequest.on('requestCompleted', () => {
        testResult.sampleData = sampleRows;

        // Now get column information
        const columnQuery = `
          SELECT 
            COLUMN_NAME,
            DATA_TYPE,
            IS_NULLABLE,
            CHARACTER_MAXIMUM_LENGTH,
            NUMERIC_PRECISION,
            NUMERIC_SCALE
          FROM INFORMATION_SCHEMA.COLUMNS 
          WHERE TABLE_NAME = '${connectionData.table_name.split('.').pop()}' 
          ORDER BY ORDINAL_POSITION
        `;

        const columnRequest = new Request(columnQuery, (err) => {
          if (err) {
            console.warn('Could not get column info:', err.message);
            // Continue without column info
            testResult.success = true;
            connection.close();
            return resolve(testResult);
          }
        });

        let columnRows = [];
        let columnMetadata = [];

        columnRequest.on('columnMetadata', (metadata) => {
          columnMetadata = metadata;
        });

        columnRequest.on('row', (row) => {
          const columnData = {};
          row.forEach((column, index) => {
            columnData[columnMetadata[index].colName] = column.value;
          });
          columnRows.push(columnData);
        });

        columnRequest.on('requestCompleted', () => {
          // Process column information
          columnRows.forEach(col => {
            let typeInfo = col.DATA_TYPE;
            if (col.CHARACTER_MAXIMUM_LENGTH) {
              typeInfo += `(${col.CHARACTER_MAXIMUM_LENGTH})`;
            } else if (col.NUMERIC_PRECISION) {
              typeInfo += `(${col.NUMERIC_PRECISION}${col.NUMERIC_SCALE ? `,${col.NUMERIC_SCALE}` : ''})`;
            }

            testResult.columnInfo[col.COLUMN_NAME] = {
              data_type: typeInfo,
              variable_range: `Type: ${col.DATA_TYPE}${col.IS_NULLABLE === 'YES' ? ' (nullable)' : ''}`
            };
          });

          testResult.success = true;
          connection.close();
          resolve(testResult);
        });

        connection.execSql(columnRequest);
      });

      connection.execSql(sampleRequest);
    });

    connection.on('error', (err) => {
      testResult.error = `Connection error: ${err.message}`;
      resolve(testResult);
    });
  });
}

// Auth endpoints
server.post('/auth/login', (req, res) => {
  const { email, password } = req.body;
  
  if (email === 'test@example.com' && password === 'Password123') {
    const user = router.db.get('users').find({ email }).value();
    const token = {
      access_token: 'mock-access-token-123',
      refresh_token: 'mock-refresh-token-123',
      token_type: 'bearer',
      expires_in: 3600
    };
    
    res.json({
      ...token,
      user: user
    });
  } else {
    res.status(401).json({ detail: 'Invalid credentials' });
  }
});

server.get('/auth/me', (req, res) => {
  const user = router.db.get('users').nth(0).value();
  res.json(user);
});

server.post('/auth/logout', (req, res) => {
  res.json({ message: 'Logged out successfully' });
});

// Connection test endpoint
server.post('/connections/test', async (req, res) => {
  const { connection_data } = req.body;
  
  if (!connection_data) {
    return res.status(400).json({ 
      detail: 'Missing connection_data in request body' 
    });
  }

  console.log('Testing connection to:', connection_data.server, connection_data.database_name);

  try {
    const result = await testSQLConnection(connection_data);
    
    if (result.success) {
      res.json({
        success: true,
        sample_data: result.sampleData,
        column_info: result.columnInfo,
        task_id: `test-${Date.now()}`
      });
    } else {
      res.status(400).json({
        success: false,
        error_message: result.error,
        task_id: `test-${Date.now()}`
      });
    }
  } catch (error) {
    console.error('Connection test error:', error);
    res.status(500).json({
      success: false,
      error_message: `Unexpected error: ${error.message}`,
      task_id: `test-${Date.now()}`
    });
  }
});

// Connection endpoints
server.get('/connections', (req, res) => {
  const connections = router.db.get('connections').value();
  res.json(connections || []);
});

server.get('/connections/:id', (req, res) => {
  const connectionId = req.params.id;
  const connection = router.db.get('connections').find({ id: connectionId }).value();
  
  if (!connection) {
    return res.status(404).json({ detail: 'Connection not found' });
  }
  
  res.json(connection);
});

// Replace the connection creation endpoint in mock-server/server.js

server.post('/connections', async (req, res) => {
  const { name, server: serverHost, database_name, username, password, table_name, driver } = req.body;
  
  if (!name || !serverHost || !database_name || !username || !password || !table_name) {
    return res.status(400).json({ 
      detail: 'Missing required fields: name, server, database_name, username, password, table_name' 
    });
  }

  const existingConnection = router.db.get('connections').find({ 
    name: name,
    user_id: 'user-123'
  }).value();
  
  if (existingConnection) {
    return res.status(400).json({ 
      detail: `You already have a connection named '${name}'` 
    });
  }

  console.log('Testing connection before creation...');
  try {
    const testResult = await testSQLConnection({
      server: serverHost,
      database_name,
      username,
      password,
      table_name
    });

    if (!testResult.success) {
      return res.status(400).json({
        detail: `Connection test failed: ${testResult.error}`
      });
    }

    console.log('Connection test successful, creating connection with schema...');
    
    // Create the connection
    const newConnection = {
      id: `conn-${Date.now()}`,
      name: name,
      server: serverHost,
      database_name: database_name,
      table_name: table_name,
      driver: driver || 'ODBC Driver 18 for SQL Server',
      status: 'test_success',
      test_successful: true,
      column_descriptions_uploaded: false,
      generated_examples_count: 0,
      total_queries: 0,
      last_queried_at: null,
      created_at: new Date().toISOString(),
      trained_at: null,
      user_id: 'user-123'
    };

    // Add to database first
    router.db.get('connections').push(newConnection).write();
    
    // AUTOMATICALLY GENERATE SCHEMA upon creation
    const schemaData = {
      connection_id: newConnection.id,
      last_refreshed: new Date().toISOString(),
      table_info: {
        total_columns: Object.keys(testResult.columnInfo).length,
        sample_rows: testResult.sampleData.length
      },
      columns: testResult.columnInfo,
      sample_data: testResult.sampleData.slice(0, 5)
    };
    
    // Store schema data immediately
    mockSchemas.set(newConnection.id, schemaData);
    
    console.log(`Connection created successfully with auto-generated schema: ${newConnection.id}`);

    res.status(201).json(newConnection);
    
  } catch (error) {
    return res.status(400).json({
      detail: `Connection test failed: ${error.message}`
    });
  }
});

// Schema refresh endpoint
server.post('/connections/:id/refresh-schema', async (req, res) => {
  const connectionId = req.params.id;
  const connection = router.db.get('connections').find({ id: connectionId }).value();
  
  if (!connection) {
    return res.status(404).json({ detail: 'Connection not found or access denied' });
  }

  console.log('Refreshing schema for connection:', connectionId);

  try {
    const testResult = await testSQLConnection({
      server: connection.server,
      database_name: connection.database_name,
      username: 'sa',
      password: 'l.messi10',
      table_name: connection.table_name
    });

    if (testResult.success) {
      const schemaData = {
        connection_id: connectionId,
        last_refreshed: new Date().toISOString(),
        table_info: {
          total_columns: Object.keys(testResult.columnInfo).length,
          sample_rows: testResult.sampleData.length
        },
        columns: testResult.columnInfo,
        sample_data: testResult.sampleData.slice(0, 5)
      };
      
      mockSchemas.set(connectionId, schemaData);
      
      const taskId = `schema-refresh-${Date.now()}`;
      
      res.json({
        task_id: taskId,
        connection_id: connectionId,
        task_type: 'refresh_schema',
        status: 'completed',
        progress: 100,
        stream_url: `/events/stream/${taskId}`,
        created_at: new Date().toISOString()
      });
    } else {
      res.status(400).json({
        detail: `Schema refresh failed: ${testResult.error}`
      });
    }
  } catch (error) {
    console.error('Schema refresh error:', error);
    res.status(500).json({
      detail: `Schema refresh failed: ${error.message}`
    });
  }
});

// Get schema endpoint
server.get('/connections/:id/schema', (req, res) => {
  const connectionId = req.params.id;
  const connection = router.db.get('connections').find({ id: connectionId }).value();
  
  if (!connection) {
    return res.status(404).json({ detail: 'Connection not found or access denied' });
  }

  const schemaData = mockSchemas.get(connectionId);
  
  if (!schemaData) {
    return res.status(404).json({ 
      detail: 'Schema not found. Try refreshing the schema first.' 
    });
  }

  res.json({
    connection_id: connectionId,
    connection_name: connection.name,
    schema: schemaData,
    last_refreshed: schemaData.last_refreshed,
    total_columns: Object.keys(schemaData.columns).length
  });
});

// Get column descriptions endpoint
server.get('/connections/:id/column-descriptions', (req, res) => {
  const connectionId = req.params.id;
  const connection = router.db.get('connections').find({ id: connectionId }).value();
  
  if (!connection) {
    return res.status(404).json({ detail: 'Connection not found or access denied' });
  }

  const schemaData = mockSchemas.get(connectionId);
  const columnDescriptions = mockColumnDescriptions.get(connectionId) || {};
  
  if (!schemaData) {
    return res.json({
      connection_id: connectionId,
      connection_name: connection.name,
      column_descriptions: [],
      total_columns: 0,
      has_descriptions: false
    });
  }

  const columnData = Object.keys(schemaData.columns).map(colName => {
    const colInfo = schemaData.columns[colName];
    return {
      column_name: colName,
      data_type: colInfo.data_type,
      variable_range: colInfo.variable_range || `Type: ${colInfo.data_type}`,
      description: columnDescriptions[colName] || '',
      has_description: !!columnDescriptions[colName],
      categories: colInfo.categories,
      range: colInfo.range,
      date_range: colInfo.date_range
    };
  });

  res.json({
    connection_id: connectionId,
    connection_name: connection.name,
    column_descriptions: columnData,
    total_columns: columnData.length,
    has_descriptions: Object.keys(columnDescriptions).length > 0
  });
});

// Update column descriptions endpoint
server.put('/connections/:id/column-descriptions', (req, res) => {
  const connectionId = req.params.id;
  const connection = router.db.get('connections').find({ id: connectionId }).value();
  
  if (!connection) {
    return res.status(404).json({ detail: 'Connection not found or access denied' });
  }

  const { columns } = req.body;
  
  if (!columns || !Array.isArray(columns)) {
    return res.status(400).json({
      detail: 'Invalid CSV format. Expected columns array.'
    });
  }

  const descriptions = {};
  columns.forEach(col => {
    if (col.column && col.description) {
      descriptions[col.column] = col.description;
    }
  });

  mockColumnDescriptions.set(connectionId, descriptions);

  const connections = router.db.get('connections');
  connections.find({ id: connectionId }).assign({ 
    column_descriptions_uploaded: Object.keys(descriptions).length > 0 
  }).write();

  res.json({
    success: true,
    message: `Updated descriptions for ${Object.keys(descriptions).length} columns`,
    connection_id: connectionId,
    total_columns: Object.keys(descriptions).length
  });
});

// CSV validation endpoint
server.post('/connections/:id/validate-csv', (req, res) => {
  const connectionId = req.params.id;
  const connection = router.db.get('connections').find({ id: connectionId }).value();
  
  if (!connection) {
    return res.status(404).json({ detail: 'Connection not found or access denied' });
  }

  const mockColumns = [
    { column_name: 'EmployeeID', description: 'Unique identifier for employee' },
    { column_name: 'EmployeeName', description: 'Full name of the employee' },
    { column_name: 'Department', description: 'Department where employee works' },
    { column_name: 'Salary', description: 'Annual salary in USD' }
  ];

  res.json({
    valid: true,
    column_count: mockColumns.length,
    columns: mockColumns,
    total_columns: mockColumns.length
  });
});


// Generate training data endpoint
server.post('/connections/:id/generate-training-data', (req, res) => {
  const connectionId = req.params.id;
  const connection = router.db.get('connections').find({ id: connectionId }).value();
  
  if (!connection) {
    return res.status(404).json({ detail: 'Connection not found or access denied' });
  }

  const { num_examples = 20 } = req.body;
  const taskId = `generate-data-${Date.now()}`;

  console.log(`Starting data generation for connection ${connectionId}, ${num_examples} examples`);

  // FIXED: Reduce timeout to 500ms so frontend polling catches it
  setTimeout(() => {
    const mockExamples = [
      {
        question: "Show me all employees in the Engineering department",
        sql: "SELECT * FROM Employees WHERE Department = 'Engineering'"
      },
      {
        question: "What is the average salary by department?",
        sql: "SELECT Department, AVG(Salary) as AvgSalary FROM Employees GROUP BY Department"
      },
      {
        question: "Find the top 5 highest paid employees",
        sql: "SELECT TOP 5 EmployeeName, Salary FROM Employees ORDER BY Salary DESC"
      },
      {
        question: "How many employees were hired in 2023?",
        sql: "SELECT COUNT(*) as HiredIn2023 FROM Employees WHERE YEAR(HireDate) = 2023"
      },
      {
        question: "List employees with salary greater than 80000",
        sql: "SELECT EmployeeName, Department, Salary FROM Employees WHERE Salary > 80000"
      },
      {
        question: "What is the minimum and maximum salary in each department?",
        sql: "SELECT Department, MIN(Salary) as MinSalary, MAX(Salary) as MaxSalary FROM Employees GROUP BY Department"
      },
      {
        question: "Show me employees hired in the last 6 months",
        sql: "SELECT * FROM Employees WHERE HireDate >= DATEADD(month, -6, GETDATE())"
      },
      {
        question: "Count employees by department",
        sql: "SELECT Department, COUNT(*) as EmployeeCount FROM Employees GROUP BY Department"
      }
    ];

    const generatedExamples = [];
    for (let i = 0; i < num_examples; i++) {
      const example = mockExamples[i % mockExamples.length];
      generatedExamples.push({
        ...example,
        id: `example-${i + 1}`,
        question: i < mockExamples.length ? example.question : `${example.question} (Variation ${i + 1})`,
      });
    }

    mockTrainingData.set(connectionId, {
      connection_id: connectionId,
      examples: generatedExamples,
      generated_at: new Date().toISOString(),
      total_examples: generatedExamples.length
    });

    const connections = router.db.get('connections');
    connections.find({ id: connectionId }).assign({ 
      status: 'data_generated',
      generated_examples_count: generatedExamples.length
    }).write();

    console.log(`Generated ${generatedExamples.length} training examples for connection ${connectionId}`);
  }, 500); // CHANGED from 2000 to 500ms

  res.json({
    task_id: taskId,
    connection_id: connectionId,
    task_type: 'generate_data',
    status: 'running',
    progress: 0,
    stream_url: `/events/stream/${taskId}`,
    created_at: new Date().toISOString()
  });
});

server.get('/connections/:id/training-data', (req, res) => {
  const connectionId = req.params.id;
  const connection = router.db.get('connections').find({ id: connectionId }).value();
  
  if (!connection) {
    return res.status(404).json({ detail: 'Connection not found or access denied' });
  }

  const trainingData = mockTrainingData.get(connectionId);
  
  if (!trainingData) {
    return res.status(404).json({ detail: 'No training data available' });
  }

  res.json({
    connection_id: connectionId,
    connection_name: connection.name,
    initial_prompt: `You are a Microsoft SQL Server expert specializing in the ${connection.table_name} table.`,
    column_descriptions: [],
    generated_examples: trainingData.examples,
    total_examples: trainingData.total_examples,
    generated_at: trainingData.generated_at
  });
});

// Train model endpoint - FIXED ROUTE TO MATCH BACKEND
server.post('/connections/:id/train', (req, res) => {
  const connectionId = req.params.id;
  const connection = router.db.get('connections').find({ id: connectionId }).value();
  
  if (!connection) {
    return res.status(404).json({ detail: 'Connection not found or access denied' });
  }

  // Allow training with test_success status (no data generation required)
  if (!['test_success', 'data_generated', 'trained'].includes(connection.status)) {
    return res.status(400).json({ 
      detail: `Connection must be successfully tested first, currently: ${connection.status}` 
    });
  }

  const taskId = `train-model-${Date.now()}`;

  console.log(`Starting model training for connection ${connectionId} (status: ${connection.status})`);

  setTimeout(() => {
    const connections = router.db.get('connections');
    connections.find({ id: connectionId }).assign({ 
      status: 'trained',
      trained_at: new Date().toISOString()
    }).write();

    console.log(`Model training completed for connection ${connectionId}`);
  }, 5000);

  res.json({
    task_id: taskId,
    connection_id: connectionId,
    task_type: 'train_model',
    status: 'running',
    progress: 0,
    stream_url: `/events/stream/${taskId}`,
    created_at: new Date().toISOString()
  });
});

// Train model endpoint - NEW ROUTE
// Replace the train-model endpoint in your mock server with this fixed version:

// Train model endpoint - FIXED: No data generation requirement
server.post('/connections/:id/train-model', (req, res) => {
  const connectionId = req.params.id;
  const connection = router.db.get('connections').find({ id: connectionId }).value();
  
  if (!connection) {
    return res.status(404).json({ detail: 'Connection not found or access denied' });
  }

  // FIXED: Allow training with test_success status (no data generation required)
  if (!['test_success', 'data_generated', 'trained'].includes(connection.status)) {
    return res.status(400).json({ 
      detail: `Connection must be successfully tested first, currently: ${connection.status}` 
    });
  }

  const taskId = `train-model-${Date.now()}`;

  console.log(`Starting model training for connection ${connectionId} (status: ${connection.status})`);

  setTimeout(() => {
    const connections = router.db.get('connections');
    connections.find({ id: connectionId }).assign({ 
      status: 'trained',
      trained_at: new Date().toISOString()
    }).write();

    console.log(`Model training completed for connection ${connectionId}`);
  }, 5000);

  res.json({
    task_id: taskId,
    connection_id: connectionId,
    task_type: 'train_model',
    status: 'running',
    progress: 0,
    stream_url: `/events/stream/${taskId}`,
    created_at: new Date().toISOString()
  });
});

// Training task management endpoints
server.get('/training/tasks/:taskId/status', (req, res) => {
  const taskId = req.params.taskId;
  const isCompleted = Date.now() - parseInt(taskId.split('-').pop()) > 3000;
  
  res.json({
    task_id: taskId,
    status: isCompleted ? 'completed' : 'running',
    progress: isCompleted ? 100 : Math.floor(Math.random() * 80) + 10,
    error_message: null,
    created_at: new Date(Date.now() - 5000).toISOString(),
    completed_at: isCompleted ? new Date().toISOString() : null
  });
});

server.get('/training/tasks', (req, res) => {
  res.json({
    tasks: [],
    total: 0,
    user_id: 'user-123'
  });
});

// Conversation endpoints
server.get('/conversations', (req, res) => {
  const conversations = router.db.get('conversations').value();
  res.json(conversations || []);
});

server.get('/conversations/:id', (req, res) => {
  const conversation = router.db.get('conversations').find({ id: req.params.id }).value();
  if (!conversation) {
    return res.status(404).json({ detail: 'Conversation not found' });
  }
  
  const messages = router.db.get('messages').filter({ conversation_id: req.params.id }).value();
  res.json({ ...conversation, messages });
});

server.post('/conversations/query', (req, res) => {
  const { question, conversation_id, connection_id } = req.body;
  let targetConversationId = conversation_id;
  let isNewConversation = false;
  let selectedConnectionId = connection_id;

  const trainedConnections = router.db.get('connections').filter({ status: 'trained' }).value();
  
  if (trainedConnections.length === 0) {
    return res.status(400).json({ 
      detail: 'No trained connections available. Please complete connection training first.' 
    });
  }

  if (!conversation_id || conversation_id === 'new') {
    if (!selectedConnectionId) {
      if (trainedConnections.length === 1) {
        selectedConnectionId = trainedConnections[0].id;
      } else {
        return res.status(400).json({ 
          detail: 'Connection selection required',
          available_connections: trainedConnections.map(c => ({ id: c.id, name: c.name }))
        });
      }
    }

    const selectedConnection = trainedConnections.find(c => c.id === selectedConnectionId);
    if (!selectedConnection) {
      return res.status(400).json({ 
        detail: 'Selected connection is not available or not trained' 
      });
    }

    const newConversation = {
      id: `conv-${Date.now()}`,
      connection_id: selectedConnectionId,
      connection_name: selectedConnection.name,
      title: question.length > 50 ? question.substring(0, 50) + '...' : question,
      description: null,
      user_id: 'user-123',
      is_active: true,
      is_pinned: false,
      connection_locked: true,
      message_count: 2,
      total_queries: 1,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      last_message_at: new Date().toISOString(),
      latest_message: question
    };
    
    router.db.get('conversations').push(newConversation).write();
    targetConversationId = newConversation.id;
    isNewConversation = true;
  } else {
    const existingConversation = router.db.get('conversations').find({ id: conversation_id }).value();
    if (!existingConversation) {
      return res.status(404).json({ detail: 'Conversation not found' });
    }
    selectedConnectionId = existingConversation.connection_id;
  }
  
  const userMessage = {
    id: `msg-user-${Date.now()}`,
    conversation_id: targetConversationId,
    content: question,
    message_type: 'user',
    is_edited: false,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString()
  };
  router.db.get('messages').push(userMessage).write();
  
  const aiMessage = {
    id: `msg-ai-${Date.now()}`,
    conversation_id: targetConversationId,
    content: "I'll help you with that query. Let me generate the SQL and fetch the results.",
    message_type: 'assistant',
    generated_sql: `SELECT TOP 10 EmployeeName, Department, Salary FROM Employees ORDER BY Salary DESC`,
    query_results: {
      data: [
        { EmployeeName: "John Smith", Department: "Engineering", Salary: 95000 },
        { EmployeeName: "Jane Doe", Department: "Marketing", Salary: 85000 },
        { EmployeeName: "Bob Johnson", Department: "Sales", Salary: 75000 }
      ],
      row_count: 3
    },
    chart_data: {
      type: 'bar',
      title: 'Top Employees by Salary',
      data: [95000, 85000, 75000],
      labels: ['John Smith', 'Jane Doe', 'Bob Johnson']
    },
    summary: "John Smith leads with the highest salary at $95,000 in Engineering, followed by Jane Doe in Marketing at $85,000.",
    execution_time: 145,
    row_count: 3,
    tokens_used: 123,
    model_used: "gpt-4",
    is_edited: false,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString()
  };
  router.db.get('messages').push(aiMessage).write();
  
  res.json({
    session_id: `session-${Date.now()}`,
    conversation_id: targetConversationId,
    user_message_id: userMessage.id,
    stream_url: `/events/stream/conversation/${targetConversationId}`,
    is_new_conversation: isNewConversation,
    connection_locked: true
  });
});

// Initialize mock data
function initializeMockData() {
  const connections = router.db.get('connections').value();
  
  connections.forEach(conn => {
    if (conn.id === 'conn-123') {
      // Mock schema for Production DB
      mockSchemas.set(conn.id, {
        connection_id: conn.id,
        last_refreshed: '2024-12-01T10:00:00Z',
        table_info: {
          total_columns: 6,
          sample_rows: 5
        },
        columns: {
          'EmployeeID': {
            data_type: 'int',
            variable_range: 'Range: 1 - 50000 (Avg: 25000)'
          },
          'EmployeeName': {
            data_type: 'varchar(100)',
            variable_range: 'Type: varchar(100)',
            categories: ['John Smith', 'Jane Doe', 'Bob Johnson', 'Alice Wilson', 'Charlie Brown']
          },
          'Department': {
            data_type: 'varchar(50)',
            variable_range: 'Type: varchar(50)',
            categories: ['Engineering', 'Marketing', 'Sales', 'HR', 'Finance']
          },
          'Salary': {
            data_type: 'decimal(10,2)',
            variable_range: 'Range: 35000.00 - 150000.00 (Avg: 75000.00)',
            range: { min: 35000, max: 150000, avg: 75000 }
          },
          'HireDate': {
            data_type: 'datetime',
            variable_range: 'Date range: 2020-01-01 to 2024-12-01',
            date_range: { min: '2020-01-01', max: '2024-12-01' }
          },
          'IsActive': {
            data_type: 'bit',
            variable_range: 'Type: bit',
            categories: ['0', '1']
          }
        },
        sample_data: [
          { EmployeeID: 1001, EmployeeName: 'John Smith', Department: 'Engineering', Salary: 95000, HireDate: '2022-03-15', IsActive: 1 },
          { EmployeeID: 1002, EmployeeName: 'Jane Doe', Department: 'Marketing', Salary: 85000, HireDate: '2021-07-20', IsActive: 1 },
          { EmployeeID: 1003, EmployeeName: 'Bob Johnson', Department: 'Sales', Salary: 75000, HireDate: '2020-11-10', IsActive: 1 },
          { EmployeeID: 1004, EmployeeName: 'Alice Wilson', Department: 'HR', Salary: 65000, HireDate: '2023-01-05', IsActive: 1 },
          { EmployeeID: 1005, EmployeeName: 'Charlie Brown', Department: 'Finance', Salary: 80000, HireDate: '2022-09-12', IsActive: 0 }
        ]
      });

      // Mock column descriptions for Production DB
      mockColumnDescriptions.set(conn.id, {
        'EmployeeID': 'Unique identifier for each employee',
        'EmployeeName': 'Full name of the employee',
        'Department': 'Department where employee works',
        'Salary': 'Annual salary in USD',
        'HireDate': 'Date when employee was hired',
        'IsActive': 'Whether employee is currently active (1) or inactive (0)'
      });

      // Mock training data for trained connection
      if (conn.status === 'trained') {
        const mockExamples = [
          {
            id: 'example-1',
            question: "Show me all employees in the Engineering department",
            sql: "SELECT * FROM Employees WHERE Department = 'Engineering'"
          },
          {
            id: 'example-2', 
            question: "What is the average salary by department?",
            sql: "SELECT Department, AVG(Salary) as AvgSalary FROM Employees GROUP BY Department"
          },
          {
            id: 'example-3',
            question: "Find the top 5 highest paid employees", 
            sql: "SELECT TOP 5 EmployeeName, Salary FROM Employees ORDER BY Salary DESC"
          }
        ];

        mockTrainingData.set(conn.id, {
          connection_id: conn.id,
          examples: mockExamples,
          generated_at: '2024-11-01T02:00:00Z',
          total_examples: mockExamples.length
        });
      }
    }
  });
}

// Call initialization after server setup
setTimeout(initializeMockData, 1000);

server.listen(6020, () => {
  console.log('Mock server running on http://localhost:6020');
  console.log('Ready to connect to MSSQL database...');
  const connections = router.db.get('connections').value();
  const conversations = router.db.get('conversations').value();
  const messages = router.db.get('messages').value();
  console.log(`Loaded: ${connections?.length || 0} connections, ${conversations?.length || 0} conversations, ${messages?.length || 0} messages`);
});