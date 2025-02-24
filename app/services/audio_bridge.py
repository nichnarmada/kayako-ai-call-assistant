import os
import asyncio
import tempfile
from typing import Dict, Optional, Callable
import websockets
from fastapi import WebSocket
from app.core.logger import logger
from app.services.deepgram_service import DeepgramService

class AudioBridge:
    """Bridge for handling audio streaming between Twilio and Deepgram."""
    
    # Store active connections by call_sid
    active_connections: Dict[str, Dict] = {}
    
    @classmethod
    async def create_connection(cls, call_sid: str, transcript_callback: Callable[[str], None]):
        """
        Create a new connection for a call.
        
        Args:
            call_sid: Twilio Call SID
            transcript_callback: Function to call with transcription results
        """
        if call_sid in cls.active_connections:
            logger.warning(f"Connection already exists for call {call_sid}")
            return
        
        try:
            # Create Deepgram STT connection
            deepgram_connection = await DeepgramService.create_stt_connection(transcript_callback)
            
            # Store connection
            cls.active_connections[call_sid] = {
                "deepgram_connection": deepgram_connection,
                "audio_buffer": bytearray(),
                "temp_file": None
            }
            
            logger.info(f"Created audio bridge for call {call_sid}")
        except Exception as e:
            logger.error(f"Error creating audio bridge for call {call_sid}: {str(e)}", exc_info=True)
            raise
    
    @classmethod
    async def handle_websocket(cls, websocket: WebSocket, call_sid: str):
        """
        Handle WebSocket connection from Twilio.
        
        Args:
            websocket: WebSocket connection
            call_sid: Twilio Call SID
        """
        if call_sid not in cls.active_connections:
            logger.error(f"No active connection for call {call_sid}")
            await websocket.close(code=1000)
            return
        
        connection = cls.active_connections[call_sid]
        deepgram_connection = connection["deepgram_connection"]
        
        try:
            # Process incoming audio data
            async for data in websocket.iter_bytes():
                # Send audio data to Deepgram
                await DeepgramService.send_audio_chunk(deepgram_connection, data)
                
                # Store audio data for potential recording
                connection["audio_buffer"].extend(data)
        except websockets.exceptions.ConnectionClosed:
            logger.info(f"WebSocket connection closed for call {call_sid}")
        except Exception as e:
            logger.error(f"Error handling WebSocket for call {call_sid}: {str(e)}", exc_info=True)
        finally:
            # Don't close the Deepgram connection here, as it might still be processing
            pass
    
    @classmethod
    async def close_connection(cls, call_sid: str):
        """
        Close connection for a call.
        
        Args:
            call_sid: Twilio Call SID
        """
        if call_sid not in cls.active_connections:
            logger.warning(f"No active connection to close for call {call_sid}")
            return
        
        connection = cls.active_connections[call_sid]
        
        try:
            # Close Deepgram connection
            await DeepgramService.close_stt_connection(connection["deepgram_connection"])
            
            # Save audio buffer to file if needed
            if len(connection["audio_buffer"]) > 0:
                # Create temp file if it doesn't exist
                if not connection["temp_file"]:
                    connection["temp_file"] = tempfile.NamedTemporaryFile(delete=False, suffix=".raw")
                    logger.info(f"Created temp file for call {call_sid}: {connection['temp_file'].name}")
                
                # Write audio buffer to file
                connection["temp_file"].write(connection["audio_buffer"])
                connection["temp_file"].flush()
            
            # Clean up
            if connection["temp_file"]:
                connection["temp_file"].close()
            
            # Remove connection
            del cls.active_connections[call_sid]
            
            logger.info(f"Closed audio bridge for call {call_sid}")
        except Exception as e:
            logger.error(f"Error closing audio bridge for call {call_sid}: {str(e)}", exc_info=True)
    
    @classmethod
    async def generate_speech(cls, text: str) -> str:
        """
        Generate speech from text and save to a temporary file.
        
        Args:
            text: Text to convert to speech
            
        Returns:
            Path to the temporary audio file
        """
        try:
            # Convert text to speech
            audio_data = await DeepgramService.text_to_speech(text)
            
            # Save to temporary file
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as temp_file:
                temp_file.write(audio_data)
                temp_file.flush()
                
                logger.info(f"Generated speech saved to {temp_file.name}")
                return temp_file.name
        except Exception as e:
            logger.error(f"Error generating speech: {str(e)}", exc_info=True)
            raise 