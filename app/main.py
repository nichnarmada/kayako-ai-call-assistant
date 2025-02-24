from fastapi import FastAPI, Request, WebSocket, Depends, Response, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from app.core.config import get_settings, Settings
from app.services.twilio_service import TwilioService
from app.services.audio_bridge import AudioBridge
from app.models.call import Conversation, CallState
from app.core.logger import logger
import httpx
import asyncio
from typing import Dict, Optional

# Initialize FastAPI app
app = FastAPI(title="Kayako AI Call Assistant")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Custom middleware to handle zrok interstitial
class ZrokMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Add skip_zrok_interstitial header to all requests
        request.headers.__dict__["_list"].append(
            (b"skip_zrok_interstitial", b"true")
        )
        response = await call_next(request)
        return response

app.add_middleware(ZrokMiddleware)

# In-memory store for active conversations
conversations: dict[str, Conversation] = {}

# Transcript callbacks by call_sid
transcript_callbacks: Dict[str, asyncio.Queue] = {}

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    logger.info("Health check requested")
    return {"status": "healthy"}

@app.post("/webhook")
async def webhook(request: Request, settings: Settings = Depends(get_settings)):
    """Handle incoming Twilio calls."""
    form_data = await request.form()
    call_sid = form_data["CallSid"]
    
    logger.info(f"New call received", extra={"call_sid": call_sid})
    
    # Initialize conversation
    conversation = TwilioService.handle_new_call(call_sid)
    conversations[call_sid] = conversation
    
    # Create a queue for transcript callbacks
    transcript_callbacks[call_sid] = asyncio.Queue()
    
    # Set up Deepgram connection
    async def transcript_callback(transcript: str):
        # Put the transcript in the queue
        if call_sid in transcript_callbacks:
            await transcript_callbacks[call_sid].put(transcript)
    
    # Set up Deepgram connection
    await TwilioService.setup_deepgram_connection(call_sid, transcript_callback)
    
    logger.info(f"Conversation initialized", extra={"call_sid": call_sid})
    
    # Create initial response asking for email
    try:
        return await TwilioService.create_response_with_tts(
            message="Thank you for calling Kayako Support. Please say your email address.",
            gather_speech=True,
            action_url="/process_email"
        )
    except Exception as e:
        logger.error(f"Error creating TTS response, falling back to Twilio TTS: {str(e)}", exc_info=True)
        return TwilioService.create_response(
            message="Thank you for calling Kayako Support. Please say your email address.",
            gather_speech=True,
            action_url="/process_email"
        )

@app.post("/process_email")
async def process_email(request: Request):
    """Process the email provided by the caller."""
    form_data = await request.form()
    call_sid = form_data["CallSid"]
    
    # Try to get email from Deepgram transcript first
    email = ""
    if call_sid in transcript_callbacks:
        try:
            # Try to get the transcript with a timeout
            email = await asyncio.wait_for(transcript_callbacks[call_sid].get(), timeout=0.1)
        except asyncio.TimeoutError:
            # If no transcript is available, fall back to Twilio's SpeechResult
            email = form_data.get("SpeechResult", "").lower()
    else:
        # Fall back to Twilio's SpeechResult
        email = form_data.get("SpeechResult", "").lower()
    
    logger.info(f"Processing email", extra={"call_sid": call_sid, "email": email})
    
    # Update conversation state
    conversation = conversations.get(call_sid)
    if not conversation:
        logger.error(f"Conversation not found", extra={"call_sid": call_sid})
        try:
            return await TwilioService.create_hangup_response_with_tts(
                "I'm sorry, but there was an error with your call. Please try again."
            )
        except Exception as e:
            logger.error(f"Error creating TTS response, falling back to Twilio TTS: {str(e)}", exc_info=True)
            return TwilioService.create_hangup_response(
                "I'm sorry, but there was an error with your call. Please try again."
            )
    
    try:
        conversation.email = email
        conversation.state = CallState.COLLECTING_ISSUE
        conversation.transcript.append(("AI", "Please say your email address."))
        conversation.transcript.append(("Customer", email))
        logger.info(f"Email processed successfully", extra={"call_sid": call_sid})
    except Exception as e:
        logger.error(f"Error processing email", extra={"call_sid": call_sid, "error": str(e)}, exc_info=True)
        try:
            return await TwilioService.create_hangup_response_with_tts(
                "I'm sorry, but there was an error processing your email. Please try again."
            )
        except Exception as e:
            logger.error(f"Error creating TTS response, falling back to Twilio TTS: {str(e)}", exc_info=True)
            return TwilioService.create_hangup_response(
                "I'm sorry, but there was an error processing your email. Please try again."
            )
    
    try:
        return await TwilioService.create_response_with_tts(
            message="Thank you. How can I assist you today?",
            gather_speech=True,
            action_url="/process_issue"
        )
    except Exception as e:
        logger.error(f"Error creating TTS response, falling back to Twilio TTS: {str(e)}", exc_info=True)
        return TwilioService.create_response(
            message="Thank you. How can I assist you today?",
            gather_speech=True,
            action_url="/process_issue"
        )

@app.post("/process_issue")
async def process_issue(request: Request):
    """Process the customer's issue."""
    form_data = await request.form()
    call_sid = form_data["CallSid"]
    
    # Try to get issue from Deepgram transcript first
    issue = ""
    if call_sid in transcript_callbacks:
        try:
            # Try to get the transcript with a timeout
            issue = await asyncio.wait_for(transcript_callbacks[call_sid].get(), timeout=0.1)
        except asyncio.TimeoutError:
            # If no transcript is available, fall back to Twilio's SpeechResult
            issue = form_data.get("SpeechResult", "")
    else:
        # Fall back to Twilio's SpeechResult
        issue = form_data.get("SpeechResult", "")
    
    logger.info(f"Processing issue", extra={"call_sid": call_sid, "issue": issue})
    
    # Update conversation state
    conversation = conversations.get(call_sid)
    if not conversation:
        logger.error(f"Conversation not found", extra={"call_sid": call_sid})
        try:
            return await TwilioService.create_hangup_response_with_tts(
                "I'm sorry, but there was an error with your call. Please try again."
            )
        except Exception as e:
            logger.error(f"Error creating TTS response, falling back to Twilio TTS: {str(e)}", exc_info=True)
            return TwilioService.create_hangup_response(
                "I'm sorry, but there was an error with your call. Please try again."
            )
    
    try:
        conversation.transcript.append(("AI", "How can I assist you today?"))
        conversation.transcript.append(("Customer", issue))
        conversation.state = CallState.PROCESSING
        logger.info(f"Issue processed successfully", extra={"call_sid": call_sid})
        
        # TODO: Implement KB search and response generation
        # For now, just respond with a placeholder message
        
        # Update conversation state
        conversation.state = CallState.COMPLETED
        
        # Close Deepgram connection
        await AudioBridge.close_connection(call_sid)
        
        # Clean up transcript callback
        if call_sid in transcript_callbacks:
            del transcript_callbacks[call_sid]
        
        try:
            return await TwilioService.create_hangup_response_with_tts(
                "Thank you for your question. I'll pass this on to our expert support team. They'll follow up shortly via email. Have a great day!"
            )
        except Exception as e:
            logger.error(f"Error creating TTS response, falling back to Twilio TTS: {str(e)}", exc_info=True)
            return TwilioService.create_hangup_response(
                "Thank you for your question. I'll pass this on to our expert support team. They'll follow up shortly via email. Have a great day!"
            )
    except Exception as e:
        logger.error(f"Error processing issue", extra={"call_sid": call_sid, "error": str(e)}, exc_info=True)
        try:
            return await TwilioService.create_hangup_response_with_tts(
                "I'm sorry, but there was an error processing your request. Our support team will follow up with you shortly."
            )
        except Exception as e:
            logger.error(f"Error creating TTS response, falling back to Twilio TTS: {str(e)}", exc_info=True)
            return TwilioService.create_hangup_response(
                "I'm sorry, but there was an error processing your request. Our support team will follow up with you shortly."
            )

@app.websocket("/audio-stream")
async def audio_stream(websocket: WebSocket, call_sid: Optional[str] = Query(None)):
    """WebSocket endpoint for real-time audio streaming with Twilio."""
    if not call_sid:
        logger.error("No call_sid provided for audio stream")
        return
    
    logger.info(f"Audio stream connection requested", extra={"call_sid": call_sid})
    
    await websocket.accept()
    try:
        # Handle the WebSocket connection
        await AudioBridge.handle_websocket(websocket, call_sid)
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected", extra={"call_sid": call_sid})
    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}", extra={"call_sid": call_sid}, exc_info=True)

# Startup and shutdown events
@app.on_event("startup")
async def startup_event():
    logger.info("Application starting up")

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Application shutting down")
    
    # Close all active connections
    for call_sid in list(AudioBridge.active_connections.keys()):
        try:
            await AudioBridge.close_connection(call_sid)
        except Exception as e:
            logger.error(f"Error closing connection for call {call_sid}: {str(e)}", exc_info=True)
        
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
