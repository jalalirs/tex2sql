import asyncio
import os
import sys
from pathlib import Path

# Add the app directory to Python path
sys.path.append(str(Path(__file__).parent))

async def verify_complete_setup():
    """Comprehensive setup verification"""
    print("🔍 Verifying Tex2SQL Setup...")
    print("=" * 50)
    
    # 1. Check environment variables
    print("1. Environment Configuration:")
    env_vars = {
        "DATABASE_URL": os.getenv("DATABASE_URL"),
        "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY"),
        "OPENAI_BASE_URL": os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
        "OPENAI_MODEL": os.getenv("OPENAI_MODEL", "gpt-4")
    }
    
    for var, value in env_vars.items():
        if value:
            if "API_KEY" in var:
                print(f"   ✅ {var}: {'*' * 10}{value[-4:] if len(value) > 4 else '****'}")
            else:
                print(f"   ✅ {var}: {value}")
        else:
            print(f"   ❌ {var}: Not set")
    
    # 2. Check database connection
    print("\n2. Database Connection:")
    try:
        from app.core.database import check_database_health
        db_healthy = await check_database_health()
        if db_healthy:
            print("   ✅ Database connection successful")
        else:
            print("   ❌ Database connection failed")
    except Exception as e:
        print(f"   ❌ Database error: {e}")
    
    # 3. Check required directories
    print("\n3. Directory Structure:")
    required_dirs = ["data", "uploads", "data/connections"]
    for dir_path in required_dirs:
        if os.path.exists(dir_path):
            print(f"   ✅ {dir_path}/")
        else:
            print(f"   ⚠️ {dir_path}/ (will be created automatically)")
            os.makedirs(dir_path, exist_ok=True)
            print(f"   ✅ {dir_path}/ (created)")
    
    # 4. Test OpenAI connection
    print("\n4. OpenAI API Connection:")
    try:
        import openai
        import httpx
        
        client = openai.OpenAI(
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
            http_client=httpx.Client(verify=False)
        )
        
        # Test with a simple completion
        response = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4"),
            messages=[{"role": "user", "content": "Say 'API test successful'"}],
            max_tokens=10
        )
        
        if response.choices[0].message.content:
            print("   ✅ OpenAI API connection successful")
        else:
            print("   ❌ OpenAI API connection failed")
    except Exception as e:
        print(f"   ❌ OpenAI API error: {e}")
    
    # 5. Check import requirements
    print("\n5. Required Packages:")
    required_packages = [
        "fastapi", "uvicorn", "sqlalchemy", "asyncpg", "pydantic", 
        "sse_starlette", "vanna", "openai", "httpx", "pyodbc", 
        "chromadb", "pandas", "plotly"
    ]
    
    for package in required_packages:
        try:
            __import__(package)
            print(f"   ✅ {package}")
        except ImportError:
            print(f"   ❌ {package} (missing)")
    
    print("\n" + "=" * 50)
    print("🎯 Setup verification complete!")

if __name__ == "__main__":
    # Load environment variables from .env file
    try:
        from dotenv import load_dotenv
        load_dotenv()
        print("✅ Loaded .env file")
    except ImportError:
        print("⚠️ python-dotenv not installed, using system environment variables")
    except Exception as e:
        print(f"⚠️ Could not load .env file: {e}")
    
    asyncio.run(verify_complete_setup())