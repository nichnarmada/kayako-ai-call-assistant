import asyncio
import os
import sys
from dotenv import load_dotenv
import websockets
import json
import base64

# Load environment variables
load_dotenv()

# Get Deepgram API key
DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")
if not DEEPGRAM_API_KEY:
    print("Error: DEEPGRAM_API_KEY environment variable not set")
    sys.exit(1)

print(f"Using Deepgram API key: {DEEPGRAM_API_KEY[:5]}...{DEEPGRAM_API_KEY[-5:]}")

async def test_stt():
    """Test Deepgram STT functionality."""
    print("Testing Deepgram STT...")
    
    # Create connection parameters
    url = "wss://api.deepgram.com/v1/listen?model=nova-2&punctuate=true&interim_results=true"
    extra_headers = {
        "Authorization": f"Token {DEEPGRAM_API_KEY}"
    }
    
    # Create connection
    try:
        print(f"Connecting to {url}")
        async with websockets.connect(url, extra_headers=extra_headers) as websocket:
            print("Connected to Deepgram STT API")
            
            # Send a simple audio file
            # You can replace this with your own audio file
            try:
                with open("test_audio.wav", "rb") as f:
                    audio_data = f.read()
                
                print(f"Sending {len(audio_data)} bytes of audio data")
                await websocket.send(audio_data)
                
                # Close the connection to indicate end of audio
                await websocket.send(json.dumps({"type": "CloseStream"}))
                
                # Process incoming messages
                async for message in websocket:
                    print(f"Received message: {message[:100]}...")
                    data = json.loads(message)
                    
                    # Check if this is a transcription result
                    if "channel" in data and "alternatives" in data["channel"]:
                        transcript = data["channel"]["alternatives"][0].get("transcript", "")
                        
                        # Only process non-empty transcripts
                        if transcript and not data.get("is_final", False):
                            print(f"Interim transcript: {transcript}")
                        
                        # Print the final transcript
                        if transcript and data.get("is_final", False):
                            print(f"Final transcript: {transcript}")
                            break
            except FileNotFoundError:
                print("Error: test_audio.wav not found")
            except Exception as e:
                print(f"Error during STT test: {str(e)}")
    except Exception as e:
        print(f"Error connecting to Deepgram STT API: {str(e)}")

async def test_tts():
    """Test Deepgram TTS functionality."""
    print("\nTesting Deepgram TTS...")
    
    # Create connection parameters
    url = "wss://api.deepgram.com/v1/speak?model=aura-asteria-en"
    extra_headers = {
        "Authorization": f"Token {DEEPGRAM_API_KEY}"
    }
    
    # Create connection
    try:
        print(f"Connecting to {url}")
        async with websockets.connect(url, extra_headers=extra_headers) as websocket:
            print("Connected to Deepgram TTS API")
            
            # Send text to convert
            text = "Hello, this is a test of the Deepgram text to speech API. How does it sound?"
            print(f"Converting text to speech: {text}")
            
            request = json.dumps({"text": text})
            print(f"Sending request: {request}")
            await websocket.send(request)
            
            # Collect audio chunks
            audio_chunks = []
            try:
                async for message in websocket:
                    print(f"Received message: {message[:100]}...")
                    data = json.loads(message)
                    
                    # Check if this is audio data
                    if "audio" in data:
                        # Decode base64 audio data
                        audio_chunk = base64.b64decode(data["audio"])
                        audio_chunks.append(audio_chunk)
                    
                    # Check if this is the end of the audio
                    if data.get("type") == "AudioEnd":
                        break
                
                # Combine audio chunks
                audio_data = b"".join(audio_chunks)
                print(f"Text-to-speech conversion complete, {len(audio_data)} bytes")
                
                # Save to file
                with open("test_tts_output.mp3", "wb") as f:
                    f.write(audio_data)
                
                print(f"Audio saved to test_tts_output.mp3")
            except websockets.exceptions.ConnectionClosedError as e:
                print(f"Connection closed: {str(e)}")
            except Exception as e:
                print(f"Error during TTS test: {str(e)}")
    except Exception as e:
        print(f"Error connecting to Deepgram TTS API: {str(e)}")

async def main():
    """Run all tests."""
    # Test TTS first since it doesn't require an audio file
    await test_tts()
    
    # Check if test audio file exists
    if os.path.exists("test_audio.wav"):
        await test_stt()
    else:
        print("\nSkipping STT test because test_audio.wav doesn't exist")
        print("To test STT, create a test_audio.wav file with speech content")

if __name__ == "__main__":
    asyncio.run(main()) 