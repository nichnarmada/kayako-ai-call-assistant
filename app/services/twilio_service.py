from twilio.twiml.voice_response import VoiceResponse
from fastapi.responses import Response
from app.models.call import Conversation, CallState, CallResponse
from app.services.audio_bridge import AudioBridge
from app.core.logger import logger
import os

class TwilioService:
    @staticmethod
    async def create_response_with_tts(message: str, gather_speech: bool = False, action_url: str | None = None) -> Response:
        """Create a TwiML response with Deepgram TTS and optional speech gathering."""
        resp = VoiceResponse()
        
        try:
            # Generate speech using Deepgram
            audio_file_path = await AudioBridge.generate_speech(message)
            
            # Use Play verb to play the generated audio
            resp.play(f"file://{audio_file_path}")
            
            # Clean up the file after a delay (Twilio needs time to fetch it)
            # This would be better handled with a proper file storage service in production
            def cleanup_file():
                try:
                    # Wait a bit to ensure Twilio has fetched the file
                    import asyncio
                    asyncio.sleep(10)
                    if os.path.exists(audio_file_path):
                        os.remove(audio_file_path)
                        logger.debug(f"Removed temporary audio file: {audio_file_path}")
                except Exception as e:
                    logger.error(f"Error removing temporary audio file: {str(e)}", exc_info=True)
            
            # Schedule cleanup
            import threading
            threading.Timer(30, cleanup_file).start()
            
        except Exception as e:
            logger.error(f"Error generating TTS, falling back to Twilio TTS: {str(e)}", exc_info=True)
            # Fallback to Twilio's TTS
            resp.say(message)
        
        if gather_speech:
            if not action_url:
                raise ValueError("action_url is required when gather_speech is True")
            
            # Use WebSocket for real-time audio streaming
            # This creates a bi-directional audio stream that we can use with Deepgram
            resp.connect().stream(url=f"/audio-stream?call_sid={{CallSid}}")
            
            # Also add a gather as fallback
            resp.gather(input="speech", action=action_url, method="POST")
            
        return Response(content=str(resp), media_type="application/xml")
    
    @staticmethod
    def create_response(message: str, gather_speech: bool = False, action_url: str | None = None) -> Response:
        """Create a TwiML response with Twilio's built-in TTS and optional speech gathering."""
        resp = VoiceResponse()
        resp.say(message)
        
        if gather_speech:
            if not action_url:
                raise ValueError("action_url is required when gather_speech is True")
            resp.gather(input="speech", action=action_url, method="POST")
            
        return Response(content=str(resp), media_type="application/xml")
    
    @staticmethod
    async def create_hangup_response_with_tts(message: str) -> Response:
        """Create a TwiML response with Deepgram TTS that says a message and hangs up."""
        resp = VoiceResponse()
        
        try:
            # Generate speech using Deepgram
            audio_file_path = await AudioBridge.generate_speech(message)
            
            # Use Play verb to play the generated audio
            resp.play(f"file://{audio_file_path}")
            
            # Clean up the file after a delay
            def cleanup_file():
                try:
                    import asyncio
                    asyncio.sleep(10)
                    if os.path.exists(audio_file_path):
                        os.remove(audio_file_path)
                except Exception as e:
                    logger.error(f"Error removing temporary audio file: {str(e)}", exc_info=True)
            
            # Schedule cleanup
            import threading
            threading.Timer(30, cleanup_file).start()
            
        except Exception as e:
            logger.error(f"Error generating TTS, falling back to Twilio TTS: {str(e)}", exc_info=True)
            # Fallback to Twilio's TTS
            resp.say(message)
        
        resp.hangup()
        return Response(content=str(resp), media_type="application/xml")
    
    @staticmethod
    def create_hangup_response(message: str) -> Response:
        """Create a TwiML response that says a message and hangs up."""
        resp = VoiceResponse()
        resp.say(message)
        resp.hangup()
        return Response(content=str(resp), media_type="application/xml")
    
    @staticmethod
    def handle_new_call(call_sid: str) -> Conversation:
        """Initialize a new conversation for a call."""
        return Conversation(
            call_sid=call_sid,
            state=CallState.COLLECTING_EMAIL
        )
        
    @staticmethod
    async def setup_deepgram_connection(call_sid: str, transcript_callback):
        """Set up Deepgram connection for a call."""
        await AudioBridge.create_connection(call_sid, transcript_callback) 