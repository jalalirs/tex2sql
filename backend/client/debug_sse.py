import asyncio
import aiohttp
import json
import re

async def test_sse_fixed():
    """Test the fixed SSE implementation"""
    
    # First, start a connection test
    connection_data = {
        "name": "tp_exposure_nlt_masked",
        "server": "10.10.68.48",
        "database_name": "PIF_DSS_PPA",
        "username": "sqldsaidt",
        "password": "3Ud*57&r%IUq",
        "table_name": "Mask.tp_exposure_nlt_masked"
    }
    
    async with aiohttp.ClientSession() as session:
        # Start connection test
        print("🧪 Starting connection test...")
        payload = {"connection_data": connection_data}
        async with session.post("http://localhost:8000/connections/test", json=payload) as resp:
            if resp.status == 200:
                result = await resp.json()
                task_id = result.get("task_id")
                print(f"✅ Test started, task ID: {task_id}")
            else:
                print(f"❌ Test failed: {resp.status}")
                print(await resp.text())
                return
        
        # Connect to SSE and parse properly
        print("📡 Connecting to SSE stream...")
        url = f"http://localhost:8000/events/stream/{task_id}"
        
        async with session.get(url, headers={'Accept': 'text/event-stream'}) as resp:
            print(f"SSE Response Status: {resp.status}")
            print(f"SSE Response Headers: {dict(resp.headers)}")
            
            if resp.status != 200:
                print(f"❌ SSE connection failed")
                return
            
            print("🔴 Connected to SSE stream - parsing events:")
            print("-" * 50)
            
            event_count = 0
            current_event = {}
            
            async for line in resp.content:
                line_str = line.decode('utf-8').rstrip('\n\r')
                
                if not line_str:
                    # Empty line indicates end of event
                    if current_event:
                        event_count += 1
                        print(f"📨 Event {event_count}:")
                        print(f"   Type: {current_event.get('event', 'unknown')}")
                        
                        # Parse and pretty print the data
                        if 'data' in current_event:
                            try:
                                data = json.loads(current_event['data'])
                                print(f"   Data: {json.dumps(data, indent=2)}")
                            except json.JSONDecodeError:
                                print(f"   Data (raw): {current_event['data']}")
                        
                        print()
                        current_event = {}
                        
                        # Stop after receiving a few events
                        if event_count >= 5:
                            print("... (stopping after 5 events)")
                            break
                            
                elif line_str.startswith('event: '):
                    current_event['event'] = line_str[7:]  # Remove 'event: ' prefix
                elif line_str.startswith('data: '):
                    current_event['data'] = line_str[6:]  # Remove 'data: ' prefix
                elif line_str.startswith('id: '):
                    current_event['id'] = line_str[4:]  # Remove 'id: ' prefix
                elif line_str.startswith(': '):
                    # Comment line (like heartbeat pings)
                    print(f"💓 Ping: {line_str}")

if __name__ == "__main__":
    asyncio.run(test_sse_fixed())