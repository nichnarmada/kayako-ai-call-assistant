import json
import asyncio
import websockets
import base64
import requests
from typing import AsyncGenerator, Dict, Any, Optional, Callable
from app.core.config import get_settings
from app.core.logger import logger

class DeepgramService:
    """Service for interacting with Deepgram's STT and TTS APIs via WebSockets."""
    
    @staticmethod
    async def create_stt_connection(callback: Callable[[str], None], call_sid: str = None) -> websockets.WebSocketClientProtocol:
        """
        Create a WebSocket connection to Deepgram's STT API.
        
        Args:
            callback: Function to call with transcription results
            call_sid: The Twilio Call SID for logging purposes
            
        Returns:
            WebSocket connection
        """
        settings = get_settings()
        api_key = settings.DEEPGRAM_API_KEY
        model = settings.DEEPGRAM_STT_MODEL
        
        # Create connection parameters
        url = f"wss://api.deepgram.com/v1/listen?model={model}&punctuate=true&interim_results=true"
        extra_headers = {
            "Authorization": f"Token {api_key}"
        }
        
        # Create connection
        logger.info("Connecting to Deepgram STT API", extra={"call_sid": call_sid} if call_sid else {})
        try:
            connection = await websockets.connect(url, extra_headers=extra_headers)
            
            # Start a background task to process incoming messages
            asyncio.create_task(DeepgramService._process_stt_messages(connection, callback, call_sid))
            
            return connection
        except Exception as e:
            logger.error(f"Error connecting to Deepgram STT API: {str(e)}", 
                         extra={"call_sid": call_sid} if call_sid else {}, 
                         exc_info=True)
            raise
    
    @staticmethod
    async def _process_stt_messages(websocket: websockets.WebSocketClientProtocol, 
                                   callback: Callable[[str], None], 
                                   call_sid: str = None):
        """Process incoming messages from Deepgram STT API."""
        try:
            async for message in websocket:
                data = json.loads(message)
                
                # Check if this is a transcription result
                if "channel" in data and "alternatives" in data["channel"]:
                    transcript = data["channel"]["alternatives"][0].get("transcript", "")
                    
                    # Only process non-empty transcripts
                    if transcript and not data.get("is_final", False):
                        logger.info(f"STT interim transcript: {transcript}", 
                                   extra={"call_sid": call_sid, "transcript_type": "interim"} if call_sid else {})
                    
                    # Call the callback with the final transcript
                    if transcript and data.get("is_final", False):
                        logger.info(f"STT final transcript: {transcript}", 
                                   extra={"call_sid": call_sid, "transcript_type": "final"} if call_sid else {})
                        callback(transcript)
        except websockets.exceptions.ConnectionClosed:
            logger.warning("Deepgram STT connection closed", 
                          extra={"call_sid": call_sid} if call_sid else {})
        except Exception as e:
            logger.error(f"Error processing Deepgram STT message: {str(e)}", 
                        extra={"call_sid": call_sid} if call_sid else {}, 
                        exc_info=True)
    
    @staticmethod
    async def send_audio_chunk(websocket: websockets.WebSocketClientProtocol, audio_chunk: bytes):
        """Send an audio chunk to Deepgram STT API."""
        try:
            await websocket.send(audio_chunk)
        except Exception as e:
            logger.error(f"Error sending audio chunk to Deepgram: {str(e)}", exc_info=True)
    
    @staticmethod
    async def close_stt_connection(websocket: websockets.WebSocketClientProtocol):
        """Close the WebSocket connection to Deepgram STT API."""
        try:
            await websocket.close()
            logger.info("Deepgram STT connection closed")
        except Exception as e:
            logger.error(f"Error closing Deepgram STT connection: {str(e)}", exc_info=True)
    
    @staticmethod
    async def text_to_speech(text: str) -> bytes:
        """
        Convert text to speech using Deepgram's TTS REST API.
        
        Args:
            text: Text to convert to speech
            
        Returns:
            Audio data as bytes
        """
        settings = get_settings()
        api_key = settings.DEEPGRAM_API_KEY
        model = settings.DEEPGRAM_TTS_MODEL
        
        # API endpoint with query parameters
        url = f"https://api.deepgram.com/v1/speak?model={model}"
        
        # Headers
        headers = {
            "Authorization": f"Token {api_key}",
            "Content-Type": "application/json"
        }
        
        # Request body - only text is required
        data = {
            "text": text
        }
        
        # Send request
        logger.info(f"Converting text to speech: {text[:50]}...")
        try:
            # Use httpx for async HTTP requests
            import httpx
            async with httpx.AsyncClient() as client:
                response = await client.post(url, headers=headers, json=data)
                
                # Check if request was successful
                if response.status_code == 200:
                    audio_data = response.content
                    logger.info(f"Text-to-speech conversion complete, {len(audio_data)} bytes")
                    return audio_data
                else:
                    logger.error(f"Text-to-speech request failed with status code: {response.status_code}")
                    logger.error(f"Response: {response.text}")
                    raise Exception(f"Text-to-speech request failed with status code: {response.status_code}")
        except Exception as e:
            logger.error(f"Error converting text to speech: {str(e)}", exc_info=True)
            raise 