import asyncio
import aiohttp
import json
import os
import time
from typing import Dict, Any, Optional, List
import csv
from pathlib import Path

# Optional imports for plotting
try:
    import matplotlib.pyplot as plt
    import pandas as pd
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

try:
    import plotly.graph_objects as go
    import plotly.offline as pyo
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False

class Tex2SQLClient:
    """Client for interacting with Tex2SQL API with authentication"""
    
    def __init__(self, base_url: str = "http://localhost:6020"):
        self.base_url = base_url.rstrip('/')
        self.session = None
        self.access_token = None
        self.refresh_token = None
        self.user_info = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    def _get_auth_headers(self) -> Dict[str, str]:
        """Get authentication headers"""
        if self.access_token:
            return {"Authorization": f"Bearer {self.access_token}"}
        return {}
    
    async def register_user(self, username: str, email: str, password: str, full_name: str = None) -> Dict[str, Any]:
        """Register a new user"""
        try:
            payload = {
                "username": username,
                "email": email,
                "password": password,
                "full_name": full_name or username
            }
            
            async with self.session.post(f"{self.base_url}/auth/register", json=payload) as response:
                if response.status == 201:
                    result = await response.json()
                    print(f"✅ User registered successfully: {result['user']['email']}")
                    return result
                elif response.status == 200:
                    result = await response.json()
                    print(f"✅ User registered successfully: {result['user']['email']}")
                    return result
                elif response.status == 400:
                    error_data = await response.json()
                    error_detail = error_data.get("detail", "Registration failed")
                    if "already registered" in error_detail.lower() or "already exists" in error_detail.lower():
                        print(f"ℹ️ User already exists: {email}")
                        return {"user_exists": True}
                    else:
                        raise Exception(f"Registration failed: {error_detail}")
                else:
                    error_text = await response.text()
                    print(f"Registration response status: {response.status}")
                    print(f"Registration response: {error_text}")
                    raise Exception(f"Registration failed: {error_text}")
        except Exception as e:
            print(f"Error registering user: {e}")
            raise
    
    async def login_user(self, email: str, password: str) -> Dict[str, Any]:
        """Login user and get tokens"""
        try:
            # Your API expects JSON with UserLogin model
            payload = {
                "email": email,
                "password": password
            }
            
            async with self.session.post(f"{self.base_url}/auth/login", json=payload) as response:
                if response.status == 200:
                    result = await response.json()
                    self.access_token = result["access_token"]
                    self.refresh_token = result.get("refresh_token")
                    print(f"✅ Login successful for: {email}")
                    
                    # Get user info
                    await self.get_current_user()
                    return result
                else:
                    error_text = await response.text()
                    print(f"Login failed with status {response.status}")
                    print(f"Response: {error_text}")
                    try:
                        error_data = await response.json()
                        error_detail = error_data.get("detail", "Login failed")
                    except:
                        error_detail = error_text
                    raise Exception(f"Login failed: {error_detail}")
                            
        except Exception as e:
            print(f"Error logging in: {e}")
            raise
    
    async def get_current_user(self) -> Dict[str, Any]:
        """Get current user information"""
        try:
            headers = self._get_auth_headers()
            async with self.session.get(f"{self.base_url}/users/me", headers=headers) as response:
                if response.status == 200:
                    self.user_info = await response.json()
                    return self.user_info
                else:
                    error = await response.text()
                    raise Exception(f"Failed to get user info: {error}")
        except Exception as e:
            print(f"Error getting user info: {e}")
            raise
    
    async def authenticate_user(self, username: str, email: str, password: str) -> bool:
        """Authenticate user - register if not exists, then login"""
        try:
            # Try to login first
            try:
                await self.login_user(email, password)
                return True
            except Exception as login_error:
                print(f"🔑 Login failed, attempting registration...")
                
                # Try to register
                try:
                    register_result = await self.register_user(username, email, password)
                    
                    if register_result.get("user_exists"):
                        # User exists but login failed - probably wrong password
                        raise Exception(f"User exists but login failed. Please check your password.")
                    
                    # Registration successful, now login
                    await self.login_user(email, password)
                    return True
                    
                except Exception as register_error:
                    print(f"❌ Both login and registration failed:")
                    print(f"   Login error: {login_error}")
                    print(f"   Registration error: {register_error}")
                    raise Exception("Authentication failed")
                    
        except Exception as e:
            print(f"❌ Authentication error: {e}")
            raise
    
    async def create_conversation(self, connection_id: str, title: str = None) -> Dict[str, Any]:
        """Create a new conversation"""
        try:
            headers = self._get_auth_headers()
            payload = {
                "connection_id": connection_id,
                "title": title or f"Conversation at {time.strftime('%Y-%m-%d %H:%M')}"
            }
            
            async with self.session.post(f"{self.base_url}/conversations/", json=payload, headers=headers) as response:
                if response.status == 200 or response.status == 201:
                    result = await response.json()
                    print(f"🔍 DEBUG: Conversation created successfully: {result.get('id', 'unknown')}")
                    return result
                else:
                    error_text = await response.text()
                    print(f"🔍 DEBUG: Conversation creation failed with status {response.status}")
                    print(f"🔍 DEBUG: Error response: {error_text}")
                    raise Exception(f"Failed to create conversation: {error_text}")
        except Exception as e:
            print(f"Error creating conversation: {e}")
            raise
    
    async def check_connection_exists(self, connection_name: str) -> Optional[Dict[str, Any]]:
        """Check if a connection exists by name"""
        try:
            headers = self._get_auth_headers()
            async with self.session.get(f"{self.base_url}/connections/", headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    for conn in data.get("connections", []):
                        if conn["name"] == connection_name:
                            return conn
            return None
        except Exception as e:
            print(f"Error checking connection: {e}")
            return None
    
    async def test_connection(self, connection_data: Dict[str, Any]) -> str:
        """Test a database connection and return task_id for SSE tracking"""
        try:
            headers = self._get_auth_headers()
            payload = {"connection_data": connection_data}
            
            async with self.session.post(f"{self.base_url}/connections/test", json=payload, headers=headers) as response:
                if response.status == 200:
                    result = await response.json()
                    return result.get("task_id")
                else:
                    error = await response.text()
                    raise Exception(f"Connection test failed: {error}")
        except Exception as e:
            print(f"Error testing connection: {e}")
            raise
    
    async def create_connection(self, connection_data: Dict[str, Any], csv_file_path: Optional[str] = None) -> Dict[str, Any]:
        """Create a new connection with optional CSV file"""
        try:
            headers = self._get_auth_headers()
            
            # Prepare form data
            data = aiohttp.FormData()
            
            # Add individual connection data fields
            for key, value in connection_data.items():
                data.add_field(key, str(value))
            
            # Add CSV file if provided
            if csv_file_path and os.path.exists(csv_file_path):
                with open(csv_file_path, 'rb') as f:
                    data.add_field('column_descriptions_file', f, 
                                 filename=os.path.basename(csv_file_path),
                                 content_type='text/csv')
            
            async with self.session.post(f"{self.base_url}/connections/", data=data, headers=headers) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    error = await response.text()
                    raise Exception(f"Failed to create connection: {error}")
                        
        except Exception as e:
            print(f"Error creating connection: {e}")
            raise
    
    async def generate_training_data(self, connection_id: str, num_examples: int = 20) -> str:
        """Generate training data and return task_id for tracking"""
        try:
            headers = self._get_auth_headers()
            payload = {
                "connection_id": connection_id,  # Add connection_id to the payload
                "num_examples": num_examples
            }
            
            async with self.session.post(f"{self.base_url}/training/connections/{connection_id}/generate-data", 
                                       json=payload, headers=headers) as response:
                if response.status == 200:
                    result = await response.json()
                    task_id = result.get("task_id")
                    print(f"🔍 DEBUG: Training data generation started with task_id: {task_id}")
                    return task_id
                else:
                    error = await response.text()
                    print(f"🔍 DEBUG: Training data generation failed with status {response.status}")
                    print(f"🔍 DEBUG: Error response: {error}")
                    raise Exception(f"Failed to start data generation: {error}")
        except Exception as e:
            print(f"Error generating training data: {e}")
            raise
    
    async def train_model(self, connection_id: str) -> str:
        """Train the model and return task_id for tracking"""
        try:
            headers = self._get_auth_headers()
            
            async with self.session.post(f"{self.base_url}/training/connections/{connection_id}/train", 
                                       headers=headers) as response:
                if response.status == 200:
                    result = await response.json()
                    return result.get("task_id")
                else:
                    error = await response.text()
                    raise Exception(f"Failed to start training: {error}")
        except Exception as e:
            print(f"Error training model: {e}")
            raise
    
    async def query_database(self, conversation_id: str, question: str) -> str:
        """Query the database through a conversation and return session_id for tracking"""
        try:
            headers = self._get_auth_headers()
            payload = {"question": question}
            
            async with self.session.post(f"{self.base_url}/conversations/{conversation_id}/query", 
                                       json=payload, headers=headers) as response:
                if response.status == 200:
                    result = await response.json()
                    return result.get("session_id")
                else:
                    error = await response.text()
                    raise Exception(f"Failed to start query: {error}")
        except Exception as e:
            print(f"Error querying database: {e}")
            raise
    
    async def stream_sse_events(self, task_id: str, timeout: int = 300):
        """Stream SSE events for a task"""
        try:
            headers = self._get_auth_headers()
            headers['Accept'] = 'text/event-stream'
            
            url = f"{self.base_url}/events/stream/{task_id}"
            
            async with self.session.get(url, headers=headers) as response:
                if response.status != 200:
                    raise Exception(f"Failed to connect to SSE stream: {response.status}")
                
                print(f"🔴 Connected to SSE stream for task: {task_id}")
                
                start_time = time.time()
                current_event = {}
                
                async for line in response.content:
                    if time.time() - start_time > timeout:
                        print("⏰ SSE stream timeout reached")
                        break
                    
                    line = line.decode('utf-8').rstrip('\n\r')
                    
                    # Handle different SSE line types
                    if line.startswith('event: '):
                        current_event['event'] = line[7:]
                    elif line.startswith('data: '):
                        current_event['data'] = line[6:]
                    elif line.startswith('id: '):
                        current_event['id'] = line[4:]
                    elif line.startswith(': '):
                        continue
                    elif line == '':
                        if current_event:
                            event_type = current_event.get('event', 'unknown')
                            
                            try:
                                if 'data' in current_event:
                                    event_data = json.loads(current_event['data'])
                                    event_data['event_type'] = event_type
                                    
                                    yield event_data
                                    
                                    if event_type in ['test_completed', 'training_completed', 'data_generation_completed', 'query_completed', 'completed', 'error']:
                                        print(f"🏁 Received completion event: {event_type}")
                                        break
                                        
                            except json.JSONDecodeError as e:
                                yield {
                                    'event_type': event_type,
                                    'raw_data': current_event.get('data', ''),
                                    'parse_error': str(e)
                                }
                            
                            current_event = {}
                    elif line.strip():
                        print(f"⚠️ Unexpected SSE line format: {repr(line)}")
                        
        except Exception as e:
            print(f"Error streaming events: {e}")
            raise

async def process_connection_workflow(config_file: str):
    """Main workflow to process a connection configuration with authentication"""
    
    # Load configuration
    if not os.path.exists(config_file):
        raise FileNotFoundError(f"Configuration file not found: {config_file}")
    
    with open(config_file, 'r') as f:
        config = json.load(f)
    
    # Check required fields
    required_fields = ["connection_name", "server", "database_name", "db_username", "db_password", "table_name", "username", "password", "email"]
    for field in required_fields:
        if field not in config:
            raise ValueError(f"Missing required field in config: {field}")
    
    # Extract auth info
    auth_username = config["username"]
    auth_password = config["password"]
    auth_email = config["email"]
    
    # Extract connection info
    connection_name = config["connection_name"]
    csv_file_path = config.get("column_description")
    
    # Prepare database connection data
    connection_data = {
        "name": connection_name,
        "server": config["server"],
        "database_name": config["database_name"],
        "username": config["db_username"],  # Database username
        "password": config["db_password"],  # Database password
        "table_name": config["table_name"],
        "driver": config.get("driver", "ODBC Driver 17 for SQL Server")
    }
    
    print(f"🚀 Starting workflow for connection: {connection_name}")
    print(f"👤 Authenticating user: {auth_email}")
    
    async with Tex2SQLClient() as client:
        # Step 1: Authenticate user
        try:
            await client.authenticate_user(auth_username, auth_email, auth_password)
            print(f"✅ Authentication successful for: {auth_email}")
        except Exception as e:
            print(f"❌ Authentication failed: {e}")
            return
        
        # Step 2: Check if connection exists
        print("🔍 Checking if connection exists...")
        existing_connection = await client.check_connection_exists(connection_name)
        
        conversation_id = None
        
        if existing_connection:
            print(f"✅ Connection '{connection_name}' already exists")
            connection_id = existing_connection["id"]
            
            # Create conversation for this connection
            print("💬 Creating conversation...")
            conversation = await client.create_conversation(connection_id, f"Query session for {connection_name}")
            conversation_id = conversation["id"]
            print(f"✅ Conversation created: {conversation_id}")
            
            # Check if it's trained
            if existing_connection.get("status") == "trained":
                print("🎯 Connection is already trained, proceeding to query...")
            else:
                print(f"⚠️ Connection exists but status is: {existing_connection.get('status', 'unknown')}")
                print("🔄 Need to complete training process...")
                
                # Complete training based on current status
                current_status = existing_connection.get("status")
                
                if current_status == "test_success":
                    # Generate data
                    print("📊 Generating training data...")
                    task_id = await client.generate_training_data(connection_id)
                    success = await track_task_progress(client, task_id, "Data Generation")
                    if not success:
                        raise Exception("Data generation failed")
                    
                    # Train model
                    print("🧠 Training model...")
                    task_id = await client.train_model(connection_id)
                    success = await track_task_progress(client, task_id, "Model Training")
                    if not success:
                        raise Exception("Model training failed")
                        
                elif current_status == "data_generated":
                    # Only need to train the model
                    print("🧠 Training model...")
                    task_id = await client.train_model(connection_id)
                    success = await track_task_progress(client, task_id, "Model Training")
                    if not success:
                        raise Exception("Model training failed")
                        
                else:
                    print(f"❌ Unexpected connection status: {current_status}")
                    print("Please check the connection manually or delete and recreate it.")
                    return
        else:
            print(f"❌ Connection '{connection_name}' does not exist, creating new one...")
            
            # Test connection first
            print("🔧 Testing database connection...")
            task_id = await client.test_connection(connection_data)
            test_success = await track_task_progress(client, task_id, "Connection Test")
            
            if not test_success:
                raise Exception("Connection test failed")
            
            # Create connection
            print("💾 Creating connection...")
            connection_result = await client.create_connection(connection_data, csv_file_path)
            connection_id = connection_result["id"]
            print(f"✅ Connection created with ID: {connection_id}")
            
            # Create conversation for this connection
            print("💬 Creating conversation...")
            conversation = await client.create_conversation(connection_id, f"Query session for {connection_name}")
            conversation_id = conversation["id"]
            print(f"✅ Conversation created: {conversation_id}")
            
            # Generate training data
            print("📊 Generating training data...")
            task_id = await client.generate_training_data(connection_id)
            await track_task_progress(client, task_id, "Data Generation")
            
            # Train model
            print("🧠 Training model...")
            task_id = await client.train_model(connection_id)
            await track_task_progress(client, task_id, "Model Training")
        
        # Step 3: Query the database through conversation
        question = "Compare the salaries of the employees"
        print(f"❓ Querying: {question}")
        session_id = await client.query_database(conversation_id, question)
        await track_query_progress(client, session_id, question)

async def track_task_progress(client: Tex2SQLClient, task_id: str, task_name: str) -> bool:
    """Track progress of a task via SSE"""
    print(f"📡 Tracking {task_name} progress...")
    
    success = False
    events_received = 0
    
    try:
        async for event in client.stream_sse_events(task_id, timeout=600):
            events_received += 1
            
            event_type = event.get("event_type", "unknown")
            print(f"  📥 Event #{events_received}: {event_type}")
            
            if event_type == "connected":
                print(f"    🔗 Connected to task stream")
                continue
                
            elif event_type == "heartbeat":
                print(f"    💓 Heartbeat")
                continue
                
            elif event_type in ["test_started", "training_started", "data_generation_started"]:
                print(f"    🚀 {task_name} started")
                continue
                
            elif event_type in ["test_progress", "training_progress", "data_generation_progress", "progress"]:
                progress = event.get("progress", 0)
                message = event.get("message", "Processing...")
                print(f"    📊 Progress: {progress}% - {message}")
                continue
                
            elif event_type == "log":
                level = event.get("level", "info")
                message = event.get("message", "")
                print(f"    📝 [{level.upper()}] {message}")
                continue
                
            elif event_type in ["test_completed", "training_completed", "data_generation_completed", "completed"]:
                success = event.get("success", False)
                if success:
                    print(f"    ✅ {task_name} completed successfully!")
                    
                    if event_type == "test_completed" and "sample_data" in event:
                        sample_count = len(event.get("sample_data", []))
                        column_count = len(event.get("column_info", {}))
                        print(f"    📊 Retrieved {sample_count} sample records with {column_count} columns")
                        
                else:
                    print(f"    ❌ {task_name} failed!")
                    error = event.get("error", event.get("error_message", "Unknown error"))
                    print(f"    ❗ Error: {error}")
                
                break
                
            elif event_type in ["test_error", "training_error", "data_generation_error", "error"]:
                print(f"    ❌ {task_name} failed!")
                error = event.get("error", event.get("error_message", event.get("message", "Unknown error")))
                print(f"    ❗ Error: {error}")
                break
                
            else:
                if "message" in event:
                    print(f"    📝 {event['message']}")
                
                if "success" in event:
                    success = event["success"]
                    if success:
                        print(f"    ✅ {task_name} completed successfully!")
                    else:
                        print(f"    ❌ {task_name} failed!")
                        if "error" in event:
                            print(f"    ❗ Error: {event['error']}")
                    break
                    
                print(f"    🔍 Unknown event data: {json.dumps(event, indent=2)}")
    
    except asyncio.TimeoutError:
        print(f"    ⏰ {task_name} timed out")
    except Exception as e:
        print(f"    ❌ Error tracking {task_name}: {e}")
    
    if events_received == 0:
        print(f"    ⚠️ No events received for {task_name}")
    
    print(f"    📊 Total events received: {events_received}")
    return success

async def track_query_progress(client: Tex2SQLClient, session_id: str, question: str):
    """Track query progress and display results"""
    print(f"📡 Tracking query progress...")
    
    query_result = {
        "sql": None,
        "data": None,
        "chart": None,
        "summary": None,
        "followup_questions": []
    }
    
    events_received = 0
    
    try:
        async for event in client.stream_sse_events(session_id, timeout=300):
            events_received += 1
            event_type = event.get("event_type", "unknown")
            print(f"  📥 Query Event #{events_received}: {event_type}")
            
            if event_type == "connected":
                print(f"    🔗 Connected to query stream")
                continue
                
            elif event_type == "heartbeat":
                print(f"    💓 Heartbeat")
                continue
                
            elif event_type in ["query_started", "sql_generated", "data_retrieved", "chart_generated", "summary_generated", "query_completed", "sql_validated", "data_fetched", "chart_skipped", "followup_generated"]:
                if "message" in event:
                    print(f"    📝 {event['message']}")
                
                if "progress" in event:
                    progress = event.get("progress", 0)
                    print(f"    📊 Progress: {progress}%")
                
                # Handle specific events
                if event_type == "sql_generated" or event_type == "sql_validated":
                    if "sql" in event:
                        query_result["sql"] = event["sql"]
                        print(f"    🔍 Generated SQL: {event['sql'][:100]}...")
                
                elif event_type == "data_fetched":
                    if "data" in event:
                        query_result["data"] = event["data"]
                        print(f"    📋 Retrieved {len(event['data'])} rows")
                    elif "row_count" in event:
                        print(f"    📋 Retrieved {event['row_count']} rows")
                
                elif event_type == "summary_generated":
                    if "summary" in event:
                        query_result["summary"] = event["summary"]
                        print(f"    📄 Summary generated")
                
                elif event_type == "followup_generated":
                    if "questions" in event:
                        query_result["followup_questions"] = event["questions"]
                        print(f"    ❓ Generated {len(event['questions'])} follow-up questions")
                
                elif event_type == "chart_generated":
                    if "chart_data" in event:
                        query_result["chart"] = event["chart_data"]
                        print(f"    📊 Chart generated successfully")
                
                elif event_type == "chart_skipped":
                    print(f"    📊 Chart generation skipped: {event.get('reason', 'Unknown reason')}")
                    query_result["chart_skipped"] = True
                
                elif event_type == "query_completed":
                    success = event.get("success", True)
                    if success:
                        print(f"    ✅ Query completed successfully!")
                        
                        # Capture any final data in the completion event
                        for key in ["sql", "data", "chart_data", "summary", "questions"]:
                            if key in event and not query_result.get(key.replace("_data", "")):
                                if key == "chart_data":
                                    query_result["chart"] = event[key]
                                elif key == "questions":
                                    query_result["followup_questions"] = event[key]
                                else:
                                    query_result[key] = event[key]
                    else:
                        print(f"    ❌ Query failed!")
                        error = event.get("error", event.get("error_message", "Unknown error"))
                        print(f"    ❗ Error: {error}")
                        return
                    break
                
                continue
                
            elif event_type in ["query_error", "error"]:
                print(f"    ❌ Query failed!")
                error = event.get("error", event.get("error_message", event.get("message", "Unknown error")))
                print(f"    ❗ Error: {error}")
                return
                
            elif event_type == "log":
                level = event.get("level", "info")
                message = event.get("message", "")
                print(f"    📝 [{level.upper()}] {message}")
                continue
                
            else:
                if "message" in event:
                    print(f"    📝 {event['message']}")
                
                if "success" in event:
                    if event["success"]:
                        print(f"    ✅ Query completed successfully!")
                        break
                    else:
                        print(f"    ❌ Query failed!")
                        if "error_message" in event:
                            print(f"    ❗ Error: {event['error_message']}")
                        return
                        
                print(f"    🔍 Unknown event data: {json.dumps(event, indent=2)}")
    
    except Exception as e:
        print(f"  ❌ Error tracking query: {e}")
        return
    
    # Display results
    print("\n" + "="*50)
    print("📊 QUERY RESULTS")
    print("="*50)
    
    print(f"\n❓ Question: {question}")
    
    if query_result["sql"]:
        print(f"\n🔍 Generated SQL:")
        print(query_result["sql"])
    
    if query_result["data"]:
        print(f"\n📋 Data:")
        for i, row in enumerate(query_result["data"]):
            print(f"  Row {i+1}: {row}")
    else:
        print(f"\n📋 No data returned")
    
    if query_result["summary"]:
        print(f"\n📄 Summary:")
        print(query_result["summary"])
    
    # Handle chart display
    if query_result["chart"]:
        print(f"\n📊 Chart data received from API:")
        try:
            if PLOTLY_AVAILABLE:
                import plotly.graph_objects as go
                from plotly.offline import plot
                
                chart_data = query_result["chart"]
                fig = go.Figure(chart_data)
                plot(fig, filename='temp_chart.html', auto_open=True)
                print(f"    ✅ Plotly chart opened in browser!")
                
            else:
                print(f"    📊 Plotly chart data available but plotly not installed")
                print(f"    Install with: pip install plotly")
                
        except Exception as e:
            print(f"    ❌ Error displaying Plotly chart: {e}")
    
    if query_result["followup_questions"]:
        print(f"\n❓ Follow-up questions:")
        for i, q in enumerate(query_result["followup_questions"], 1):
            print(f"  {i}. {q}")
    
    print(f"\n📊 Total events received: {events_received}")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) != 2:
        print("Usage: python tex2sql_client.py <config_file.json>")
        print("\nConfig file should contain:")
        print("{")
        print('  "connection_name": "your_connection_name",')
        print('  "server": "localhost,1433",')
        print('  "database_name": "your_database",')
        print('  "db_username": "database_user",')
        print('  "db_password": "database_password",')
        print('  "table_name": "your_table",')
        print('  "driver": "ODBC Driver 18 for SQL Server",')
        print('  "username": "app_username",')
        print('  "password": "app_password",')
        print('  "email": "user@example.com"')
        print("}")
        sys.exit(1)
    
    config_file = sys.argv[1]
    
    try:
        asyncio.run(process_connection_workflow(config_file))
    except KeyboardInterrupt:
        print("\n🛑 Interrupted by user")
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)