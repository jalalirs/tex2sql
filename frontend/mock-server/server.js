const jsonServer = require('json-server');
const server = jsonServer.create();
const router = jsonServer.router('db.json');
const middlewares = jsonServer.defaults();

server.use(middlewares);
server.use(jsonServer.bodyParser);

// Custom auth routes
server.post('/auth/login', (req, res) => {
  const { email, password } = req.body;
  
  if (email === 'test@example.com' && password === 'password123') {
    const user = router.db.get('users').find({ email }).value();
    const tokens = router.db.get('auth_tokens').value();
    const token = tokens && tokens.length > 0 ? tokens[0] : {
      access_token: 'mock-access-token-123',
      refresh_token: 'mock-refresh-token-123',
      token_type: 'bearer',
      expires_in: 3600
    };
    
    res.json({
      access_token: token.access_token,
      refresh_token: token.refresh_token,
      token_type: token.token_type,
      expires_in: token.expires_in,
      user: user
    });
  } else {
    res.status(401).json({ detail: 'Invalid credentials' });
  }
});

server.post('/auth/register', (req, res) => {
  const { email, username, password, full_name, company, job_title } = req.body;
  
  const newUser = {
    id: `user-${Date.now()}`,
    email,
    username,
    full_name: full_name || '',
    role: 'user',
    is_active: true,
    is_verified: false,
    company: company || '',
    job_title: job_title || '',
    created_at: new Date().toISOString()
  };
  
  router.db.get('users').push(newUser).write();
  
  const token = router.db.get('auth_tokens').nth(0).value();
  
  res.status(201).json({
    access_token: token.access_token,
    refresh_token: token.refresh_token,
    token_type: token.token_type,
    expires_in: token.expires_in,
    user: newUser
  });
});

server.get('/auth/me', (req, res) => {
  const user = router.db.get('users').nth(0).value();
  res.json(user);
});

server.post('/auth/logout', (req, res) => {
  res.json({ message: 'Logged out successfully' });
});

// Mock conversation query
server.post('/conversations/query', (req, res) => {
  const { question, conversation_id } = req.body;
  
  res.json({
    session_id: `session-${Date.now()}`,
    conversation_id: conversation_id || `conv-${Date.now()}`,
    user_message_id: `msg-${Date.now()}`,
    stream_url: `/events/stream/conversation/${conversation_id || 'new'}`,
    is_new_conversation: !conversation_id,
    connection_locked: true
  });
});

// Mock connection test
server.post('/connections/test', (req, res) => {
  res.json({
    success: true,
    task_id: `task-${Date.now()}`,
    sample_data: [
      { id: 1, name: 'Product A', price: 99.99 },
      { id: 2, name: 'Product B', price: 149.99 }
    ],
    column_info: {
      id: 'int',
      name: 'varchar(255)', 
      price: 'decimal(10,2)'
    }
  });
});

server.use(router);
server.listen(6020, () => {
  console.log('Mock server is running on http://localhost:6020');
});