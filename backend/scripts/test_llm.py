#!/usr/bin/env python3
"""
Simple OpenAI API test script with custom base URL and SSL verification disabled
"""

import openai
import httpx
import os
from typing import Optional

def test_openai_api(
    api_key: str,
    base_url: str,
    model: str = "gpt-3.5-turbo",
    message: str = "Hello! Can you respond with a simple greeting?"
) -> None:
    """
    Test OpenAI API with custom configuration
    
    Args:
        api_key: Your OpenAI API key
        base_url: Custom base URL for the API
        model: Model name to use
        message: Test message to send
    """
    
    try:
        # Create OpenAI client with custom configuration
        print(base_url)
        client = openai.OpenAI(
            base_url=base_url,
            api_key=api_key,
            http_client=httpx.Client(verify=False)
        )
        
        print("🚀 Testing OpenAI API connection...")
        print(f"📡 Base URL: {base_url}")
        print(f"🤖 Model: {model}")
        print(f"💬 Message: {message}")
        print("-" * 50)
        
        # Make a simple chat completion request
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "user", 
                    "content": message
                }
            ],
            max_tokens=150,
            temperature=0.7
        )
        
        # Print the response
        print("✅ API Response received!")
        print(f"📝 Response: {response.choices[0].message.content}")
        print(f"🔧 Model used: {response.model}")
        print(f"🎯 Tokens used: {response.usage.total_tokens}")
        
    except Exception as e:
        print(f"❌ Error occurred: {str(e)}")
        print(f"🔍 Error type: {type(e).__name__}")

def test_streaming_api(
    api_key: str,
    base_url: str,
    model: str = "gpt-3.5-turbo",
    message: str = "Write a short poem about coding"
) -> None:
    """
    Test streaming API response
    """
    
    try:
        client = openai.OpenAI(
            #base_url=base_url,
            api_key=api_key,
            http_client=httpx.Client(verify=False)
        )
        
        print("\n🌊 Testing Streaming API...")
        print(f"💬 Message: {message}")
        print("-" * 50)
        print("📝 Streaming response:")
        
        # Create streaming request
        stream = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "user",
                    "content": message
                }
            ],
            max_tokens=200,
            temperature=0.7,
            stream=True
        )
        
        # Print streaming response
        for chunk in stream:
            if chunk.choices[0].delta.content is not None:
                print(chunk.choices[0].delta.content, end="", flush=True)
        
        print("\n✅ Streaming completed!")
        
    except Exception as e:
        print(f"❌ Streaming error: {str(e)}")

def test_models_list(api_key: str, base_url: str) -> None:
    """
    Test listing available models
    """
    
    try:
        client = openai.OpenAI(
            #base_url=base_url,
            api_key=api_key,
            http_client=httpx.Client(verify=False)
        )
        
        print("\n📋 Testing Models List API...")
        print("-" * 50)
        
        # List available models
        models = client.models.list()
        
        print("✅ Available models:")
        for model in models.data[:5]:  # Show first 5 models
            print(f"  🤖 {model.id}")
        
        if len(models.data) > 5:
            print(f"  ... and {len(models.data) - 5} more models")
            
    except Exception as e:
        print(f"❌ Models list error: {str(e)}")

def main():
    """
    Main function to run API tests
    """
    
    # Configuration - Update these values
    API_KEY = ""  # Replace with your actual API key
    BASE_URL = "https://api.openai.com/v1"  # Replace with your custom base URL
    MODEL = "gpt-3.5-turbo"  # Replace with your preferred model
    
    # You can also use environment variables
    API_KEY = os.getenv("OPENAI_API_KEY", API_KEY)
    BASE_URL = os.getenv("OPENAI_BASE_URL", BASE_URL)
    MODEL = os.getenv("OPENAI_MODEL", MODEL)
    
    # Validate configuration
    if API_KEY == "your-api-key-here" or not API_KEY:
        print("❌ Error: Please set your API key!")
        print("💡 Set OPENAI_API_KEY environment variable or update the script")
        return
    
    print("🧪 OpenAI API Test Script")
    print("=" * 50)
    
    # Test basic chat completion
    test_openai_api(
        api_key=API_KEY,
        base_url=BASE_URL,
        model=MODEL,
        message="Hello! Please respond with a simple greeting."
    )
    
    # Test streaming
    test_streaming_api(
        api_key=API_KEY,
        base_url=BASE_URL,
        model=MODEL,
        message="Write a haiku about programming"
    )
    
    # Test models list
    test_models_list(
        api_key=API_KEY,
        base_url=BASE_URL
    )
    
    print("\n🎉 All tests completed!")

if __name__ == "__main__":
    main()