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
    """Client for interacting with Tex2SQL API"""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url.rstrip('/')
        self.session = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def check_connection_exists(self, connection_name: str) -> Optional[Dict[str, Any]]:
        """Check if a connection exists by name"""
        try:
            async with self.session.get(f"{self.base_url}/connections/") as response:
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
            payload = {"connection_data": connection_data}
            async with self.session.post(f"{self.base_url}/connections/test", json=payload) as response:
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
            # Your API expects form data with individual fields
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
            
            async with self.session.post(f"{self.base_url}/connections/", data=data) as response:
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
            payload = {"connection_id": connection_id, "num_examples": num_examples}
            async with self.session.post(f"{self.base_url}/training/connections/{connection_id}/generate-data", json=payload) as response:
                if response.status == 200:
                    result = await response.json()
                    return result.get("task_id")
                else:
                    error = await response.text()
                    raise Exception(f"Failed to start data generation: {error}")
        except Exception as e:
            print(f"Error generating training data: {e}")
            raise
    
    async def train_model(self, connection_id: str) -> str:
        """Train the model and return task_id for tracking"""
        try:
            async with self.session.post(f"{self.base_url}/training/connections/{connection_id}/train") as response:
                if response.status == 200:
                    result = await response.json()
                    return result.get("task_id")
                else:
                    error = await response.text()
                    raise Exception(f"Failed to start training: {error}")
        except Exception as e:
            print(f"Error training model: {e}")
            raise
    
    async def query_database(self, connection_id: str, question: str) -> str:
        """Query the database and return session_id for tracking"""
        try:
            payload = {"question": question, "chat_history": []}
            async with self.session.post(f"{self.base_url}/chat/connections/{connection_id}/query", json=payload) as response:
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
        """Stream SSE events for a task - COMPLETELY FIXED VERSION"""
        try:
            url = f"{self.base_url}/events/stream/{task_id}"
            
            async with self.session.get(url, headers={'Accept': 'text/event-stream'}) as response:
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
                        current_event['event'] = line[7:]  # Remove 'event: ' prefix
                    elif line.startswith('data: '):
                        current_event['data'] = line[6:]  # Remove 'data: ' prefix
                    elif line.startswith('id: '):
                        current_event['id'] = line[4:]  # Remove 'id: ' prefix
                    elif line.startswith(': '):
                        # Comment/ping line - ignore but continue
                        continue
                    elif line == '':
                        # Empty line indicates end of event
                        if current_event:
                            # Process the complete event
                            event_type = current_event.get('event', 'unknown')
                            
                            try:
                                # Parse JSON data
                                if 'data' in current_event:
                                    event_data = json.loads(current_event['data'])
                                    event_data['event_type'] = event_type
                                    
                                    yield event_data
                                    
                                    # Check if this is a completion event that should close the stream
                                    if event_type in ['test_completed', 'training_completed', 'data_generation_completed', 'query_completed', 'query_result', 'completed', 'error']:
                                        print(f"🏁 Received completion event: {event_type}")
                                        break
                                        
                            except json.JSONDecodeError as e:
                                # If JSON parsing fails, yield raw data
                                yield {
                                    'event_type': event_type,
                                    'raw_data': current_event.get('data', ''),
                                    'parse_error': str(e)
                                }
                            
                            # Reset for next event
                            current_event = {}
                    
                    # If we get here with non-empty line that doesn't match patterns, it might be malformed
                    elif line.strip():
                        print(f"⚠️ Unexpected SSE line format: {repr(line)}")
                        
        except Exception as e:
            print(f"Error streaming events: {e}")
            raise

async def process_connection_workflow(config_file: str):
    """Main workflow to process a connection configuration"""
    
    # Load configuration
    if not os.path.exists(config_file):
        raise FileNotFoundError(f"Configuration file not found: {config_file}")
    
    with open(config_file, 'r') as f:
        config = json.load(f)
    
    required_fields = ["connection_name", "server", "database_name", "username", "password", "table_name"]
    for field in required_fields:
        if field not in config:
            raise ValueError(f"Missing required field in config: {field}")
    
    connection_name = config["connection_name"]
    csv_file_path = config.get("column_description")
    
    # Prepare connection data
    connection_data = {
        "name": connection_name,
        "server": config["server"],
        "database_name": config["database_name"],
        "username": config["username"],
        "password": config["password"],
        "table_name": config["table_name"]
    }
    
    print(f"🚀 Starting workflow for connection: {connection_name}")
    
    async with Tex2SQLClient() as client:
        # Check if connection exists
        print("🔍 Checking if connection exists...")
        existing_connection = await client.check_connection_exists(connection_name)
        
        if existing_connection:
            print(f"✅ Connection '{connection_name}' already exists")
            connection_id = existing_connection["id"]
            
            # Check if it's trained
            if existing_connection.get("status") == "trained":
                print("🎯 Connection is already trained, proceeding to query...")
            else:
                print(f"⚠️ Connection exists but status is: {existing_connection.get('status', 'unknown')}")
                print("🔄 Need to complete training process...")
                
                # Check what stage we're at and continue from there
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
            
            # Generate training data
            print("📊 Generating training data...")
            task_id = await client.generate_training_data(connection_id)
            await track_task_progress(client, task_id, "Data Generation")
            
            # Train model
            print("🧠 Training model...")
            task_id = await client.train_model(connection_id)
            await track_task_progress(client, task_id, "Model Training")
        
        # Query the database
        question = "what is the market value over time for the construction sector"
        print(f"❓ Querying: {question}")
        session_id = await client.query_database(connection_id, question)
        await track_query_progress(client, session_id, question)

async def track_task_progress(client: Tex2SQLClient, task_id: str, task_name: str) -> bool:
    """Track progress of a task via SSE - COMPLETELY FIXED VERSION"""
    print(f"📡 Tracking {task_name} progress...")
    
    success = False
    events_received = 0
    
    try:
        async for event in client.stream_sse_events(task_id, timeout=600):  # 10 minutes timeout
            events_received += 1
            
            event_type = event.get("event_type", "unknown")
            print(f"  📥 Event #{events_received}: {event_type}")
            
            # Handle different event types
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
                source = event.get("source", "system")
                print(f"    📝 [{level.upper()}] {message}")
                continue
                
            elif event_type in ["test_completed", "training_completed", "data_generation_completed"]:
                success = event.get("success", False)
                if success:
                    print(f"    ✅ {task_name} completed successfully!")
                    
                    # Show additional info for test completion
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
                # Handle any other event types
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
                    
                # Print unknown events for debugging
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
    """Track query progress and display results - FIXED VERSION"""
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
        async for event in client.stream_sse_events(session_id, timeout=300):  # 5 minutes timeout
            events_received += 1
            event_type = event.get("event_type", "unknown")
            print(f"  📥 Query Event #{events_received}: {event_type}")
            
            if event_type == "connected":
                print(f"    🔗 Connected to query stream")
                continue
                
            elif event_type == "heartbeat":
                print(f"    💓 Heartbeat")
                continue
                
            elif event_type in ["query_started", "sql_generated", "data_retrieved", "chart_generated", "summary_generated", "query_result", "sql_validated", "data_fetched", "chart_skipped", "followup_generated"]:
                if "message" in event:
                    print(f"    📝 {event['message']}")
                
                if "progress" in event:
                    progress = event.get("progress", 0)
                    print(f"    📊 Progress: {progress}%")
                
                # Handle query_result event (complete result)
                if event_type == "query_result":
                    print(f"    ✅ Query completed successfully!")
                    
                    # Capture all data from the complete result
                    if "sql" in event:
                        query_result["sql"] = event["sql"]
                        print(f"    🔍 Generated SQL: {event['sql'][:100]}...")
                    
                    if "data_rows" in event:
                        print(f"    📋 Retrieved {event['data_rows']} rows")
                    
                    if "has_chart" in event and event["has_chart"]:
                        print(f"    📊 Chart data available")
                        query_result["chart"] = True
                    
                    if "summary" in event:
                        print(f"    📄 Summary generated")
                        query_result["summary"] = event["summary"]
                    
                    if "followup_questions" in event:
                        print(f"    ❓ Generated {len(event['followup_questions'])} follow-up questions")
                        query_result["followup_questions"] = event["followup_questions"]
                    
                    # This is a completion event, so break
                    break
                
                # Handle individual step events
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
                
                # Legacy handling for other events
                if "row_count" in event and event_type != "data_fetched":
                    print(f"    📋 Retrieved {event['row_count']} rows")
                    if "preview_data" in event:
                        query_result["data"] = event["preview_data"]
                    elif "data" in event:
                        query_result["data"] = event["data"]
                
                if "chart_data" in event:
                    print(f"    📊 Chart generated")
                    query_result["chart"] = event["chart_data"]
                
                if "summary" in event and event_type != "summary_generated":
                    print(f"    📄 Summary generated")
                    query_result["summary"] = event["summary"]
                
                if "questions" in event and event_type != "followup_generated":
                    print(f"    ❓ Generated {len(event['questions'])} follow-up questions")
                    query_result["followup_questions"] = event["questions"]
                    
                continue
                
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
                # Handle any other event types
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
                        
                # Print unknown events for debugging
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
                # Handle Plotly chart data from your API
                import plotly.graph_objects as go
                from plotly.offline import plot
                
                chart_data = query_result["chart"]
                
                # Recreate the Plotly figure from JSON
                fig = go.Figure(chart_data)
                
                # Display the chart
                plot(fig, filename='temp_chart.html', auto_open=True)
                print(f"    ✅ Plotly chart opened in browser!")
                
            else:
                print(f"    📊 Plotly chart data available but plotly not installed")
                print(f"    Install with: pip install plotly")
                
        except Exception as e:
            print(f"    ❌ Error displaying Plotly chart: {e}")
            # Fallback to showing chart data structure
            print(f"    Chart data keys: {list(query_result['chart'].keys()) if isinstance(query_result['chart'], dict) else 'Not a dict'}")
    
    elif query_result.get("chart_skipped"):
        print(f"\n📊 Chart generation was skipped by the API")
        
        # Create our own chart since API didn't generate one
        if query_result["data"] and len(query_result["data"]) > 1:
            try:
                if MATPLOTLIB_AVAILABLE:
                    import matplotlib.pyplot as plt
                    import pandas as pd
                    
                    # Convert data to DataFrame
                    df = pd.DataFrame(query_result["data"])
                    
                    # Convert string numbers to actual numbers
                    for col in df.columns:
                        if col.lower() not in ['year', 'date', 'time'] and df[col].dtype == 'object':
                            try:
                                df[col] = pd.to_numeric(df[col], errors='ignore')
                            except:
                                pass
                    
                    print(f"    📊 Creating fallback chart with matplotlib...")
                    
                    # Special handling for Year/Value data (like your construction sector query)
                    if 'Year' in df.columns and len(df.columns) == 2:
                        value_col = [col for col in df.columns if col != 'Year'][0]
                        
                        plt.figure(figsize=(12, 8))
                        
                        # Convert values to billions for better readability
                        values = df[value_col].astype(float) / 1e9
                        years = df['Year'].astype(str)
                        
                        # Create bar chart with trend line
                        bars = plt.bar(years, values, alpha=0.7, color=['#1f77b4', '#ff7f0e', '#2ca02c'])
                        plt.plot(years, values, 'ro-', linewidth=2, markersize=8)
                        
                        # Add value labels on bars
                        for i, (year, value) in enumerate(zip(years, values)):
                            plt.text(i, value + max(values) * 0.02, f'${value:.1f}B', 
                                    ha='center', va='bottom', fontweight='bold')
                        
                        plt.title('Construction Sector Market Value Over Time', fontsize=16, fontweight='bold')
                        plt.xlabel('Year', fontsize=12)
                        plt.ylabel('Total Market Value (Billions USD)', fontsize=12)
                        plt.grid(True, alpha=0.3)
                        
                        # Color bars based on trend
                        for i, bar in enumerate(bars):
                            if i > 0:
                                if values.iloc[i] > values.iloc[i-1]:
                                    bar.set_color('#2ca02c')  # Green for increase
                                else:
                                    bar.set_color('#d62728')  # Red for decrease
                        
                        plt.tight_layout()
                        plt.show()
                        print(f"    ✅ Fallback chart displayed successfully!")
                        
                        # Also show trend analysis
                        print(f"\n📈 Trend Analysis:")
                        for i in range(1, len(values)):
                            change = values.iloc[i] - values.iloc[i-1]
                            pct_change = (change / values.iloc[i-1]) * 100
                            direction = "📈" if change > 0 else "📉"
                            print(f"    {years.iloc[i-1]} → {years.iloc[i]}: {direction} ${change:+.1f}B ({pct_change:+.1f}%)")
                    
                    elif len(df.select_dtypes(include=['number']).columns) >= 1:
                        # Generic chart for other data types
                        numeric_cols = df.select_dtypes(include=['number']).columns
                        
                        plt.figure(figsize=(10, 6))
                        
                        if len(numeric_cols) >= 2:
                            # Scatter plot
                            plt.scatter(df[numeric_cols[0]], df[numeric_cols[1]], alpha=0.6, s=100)
                            plt.xlabel(str(numeric_cols[0]))
                            plt.ylabel(str(numeric_cols[1]))
                            plt.title(f'{numeric_cols[0]} vs {numeric_cols[1]}')
                        else:
                            # Bar chart
                            x_vals = range(len(df))
                            plt.bar(x_vals, df[numeric_cols[0]])
                            plt.xlabel('Records')
                            plt.ylabel(str(numeric_cols[0]))
                            plt.title(f'{numeric_cols[0]} Distribution')
                        
                        plt.grid(True, alpha=0.3)
                        plt.tight_layout()
                        plt.show()
                        print(f"    ✅ Fallback chart displayed successfully!")
                
                else:
                    print(f"    📊 Install matplotlib and pandas for fallback charts:")
                    print(f"    pip install matplotlib pandas")
                    
            except Exception as e:
                print(f"    📊 Could not create fallback chart: {e}")
    else:
        print(f"\n📊 No chart generated for this query")
    
    if query_result["followup_questions"]:
        print(f"\n❓ Follow-up questions:")
        for i, q in enumerate(query_result["followup_questions"], 1):
            print(f"  {i}. {q}")
    
    print(f"\n📊 Total events received: {events_received}")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) != 2:
        print("Usage: python tex2sql_client.py <config_file.json>")
        sys.exit(1)
    
    config_file = sys.argv[1]
    
    try:
        asyncio.run(process_connection_workflow(config_file))
    except KeyboardInterrupt:
        print("\n🛑 Interrupted by user")
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)