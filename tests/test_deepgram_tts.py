import os
import requests
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get Deepgram API key
DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")
if not DEEPGRAM_API_KEY:
    print("Error: DEEPGRAM_API_KEY environment variable not set")
    exit(1)

print(f"Using Deepgram API key: {DEEPGRAM_API_KEY[:5]}...{DEEPGRAM_API_KEY[-5:]}")

def test_tts_rest_api():
    """Test Deepgram TTS functionality using the REST API."""
    print("\nTesting Deepgram TTS using REST API...")
    
    # API endpoint with query parameters
    url = "https://api.deepgram.com/v1/speak?model=aura-asteria-en"
    
    # Headers
    headers = {
        "Authorization": f"Token {DEEPGRAM_API_KEY}",
        "Content-Type": "application/json"
    }
    
    # Request body - only text is required
    data = {
        "text": "Hello, this is a test of the Deepgram text to speech API. How does it sound?"
    }
    
    print(f"Sending request to {url}")
    print(f"Request data: {json.dumps(data)}")
    
    # Send request
    try:
        response = requests.post(url, headers=headers, json=data)
        
        # Check if request was successful
        if response.status_code == 200:
            print(f"Request successful! Status code: {response.status_code}")
            
            # Save audio to file
            with open("test_tts_rest_output.mp3", "wb") as f:
                f.write(response.content)
            
            print(f"Audio saved to test_tts_rest_output.mp3 ({len(response.content)} bytes)")
        else:
            print(f"Request failed with status code: {response.status_code}")
            print(f"Response: {response.text}")
    except Exception as e:
        print(f"Error during TTS test: {str(e)}")

if __name__ == "__main__":
    test_tts_rest_api() 