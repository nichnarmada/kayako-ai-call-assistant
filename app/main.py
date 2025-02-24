from fastapi import FastAPI, Request, WebSocket, Depends, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from app.core.config import get_settings, Settings
from app.services.twilio_service import TwilioService
from app.models.call import Conversation
from app.core.logger import logger
import httpx

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
    
    logger.info(f"Conversation initialized", extra={"call_sid": call_sid})
    
    # Create initial response asking for email
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
    email = form_data.get("SpeechResult", "").lower()
    
    logger.info(f"Processing email", extra={"call_sid": call_sid, "email": email})
    
    # Update conversation state
    conversation = conversations.get(call_sid)
    if not conversation:
        logger.error(f"Conversation not found", extra={"call_sid": call_sid})
        return TwilioService.create_hangup_response(
            "I'm sorry, but there was an error with your call. Please try again."
        )
    
    try:
        conversation.email = email
        conversation.state = "COLLECTING_ISSUE"
        conversation.transcript.append(("AI", "Please say your email address."))
        conversation.transcript.append(("Customer", email))
        logger.info(f"Email processed successfully", extra={"call_sid": call_sid})
    except Exception as e:
        logger.error(f"Error processing email", extra={"call_sid": call_sid, "error": str(e)}, exc_info=True)
        return TwilioService.create_hangup_response(
            "I'm sorry, but there was an error processing your email. Please try again."
        )
    
    return TwilioService.create_response(
        message="Thank you. How can I assist you today?",
        gather_speech=True,
        action_url="/process_issue"
    )

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time audio streaming."""
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            logger.debug(f"WebSocket message received: {data[:100]}...")  # Log first 100 chars
            await websocket.send_text(f"Message text was: {data}")
    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}", exc_info=True)

# Startup and shutdown events
@app.on_event("startup")
async def startup_event():
    logger.info("Application starting up")

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Application shutting down")
        
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
