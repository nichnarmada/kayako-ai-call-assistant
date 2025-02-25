from fastapi import FastAPI, Request, WebSocket, Depends, Response, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from app.core.config import get_settings, Settings
from app.services.twilio_service import TwilioService
from app.services.audio_bridge import AudioBridge
from app.models.call import Conversation, CallState
from app.core.logger import logger
from app.services.kayako_service import KayakoService
from app.services.openai_service import OpenAIService
import httpx
import asyncio
from typing import Dict, Optional, Any
import os
from fastapi.responses import FileResponse
from tempfile import gettempdir

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

# Store processing results by call_sid
processing_results: Dict[str, Dict[str, Any]] = {}

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    logger.info("Health check requested")
    return {"status": "healthy"}

@app.post("/")
async def root_webhook(request: Request, settings: Settings = Depends(get_settings)):
    """Root endpoint that redirects to the webhook endpoint for Twilio calls."""
    logger.info("Received request at root endpoint, redirecting to /webhook")
    return await webhook(request, settings)

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
    
    # Create initial response with greeting
    try:
        return await TwilioService.create_response_with_tts(
            message="Thank you for calling Kayako Support. How can I assist you today?",
            gather_speech=True,
            action_url="/process_issue"
        )
    except Exception as e:
        logger.error(f"Error creating TTS response, falling back to Twilio TTS: {str(e)}", exc_info=True)
        return TwilioService.create_response(
            message="Thank you for calling Kayako Support. How can I assist you today?",
            gather_speech=True,
            action_url="/process_issue"
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
        conversation.transcript.append(("Customer", email))
        logger.info(f"Email processed successfully", extra={"call_sid": call_sid})
        
        # Check if we already have an issue
        if len(conversation.transcript) >= 2 and conversation.transcript[1][0] == "Customer":
            # We already have the issue, so we can create a ticket or provide the answer
            issue = conversation.transcript[1][1]
            
            # Check if we have a response from OpenAI
            if len(conversation.transcript) >= 3 and conversation.transcript[2][0] == "AI":
                response_message = conversation.transcript[2][1]
                
                # Check if the response indicates an answer was found
                answer_found = "human agent" not in response_message.lower() and "follow up" not in response_message.lower() and "pass this on" not in response_message.lower()
                
                if answer_found:
                    # If an answer was found, respond and end the call
                    conversation.state = CallState.COMPLETED
                    
                    # Close Deepgram connection
                    await AudioBridge.close_connection(call_sid)
                    
                    # Clean up transcript callback
                    if call_sid in transcript_callbacks:
                        del transcript_callbacks[call_sid]
                    
                    try:
                        return await TwilioService.create_hangup_response_with_tts(
                            f"Thank you for providing your email. {response_message} Have a great day!"
                        )
                    except Exception as e:
                        logger.error(f"Error creating TTS response, falling back to Twilio TTS: {str(e)}", exc_info=True)
                        return TwilioService.create_hangup_response(
                            f"Thank you for providing your email. {response_message} Have a great day!"
                        )
                else:
                    # If no answer was found, create a ticket and escalate
                    conversation.state = CallState.PROCESSING
                    
                    # Generate ticket summary
                    ticket_data = await OpenAIService.create_ticket_summary(conversation.transcript)
                    
                    # Create ticket in Kayako
                    try:
                        ticket = await KayakoService.create_ticket(
                            email=conversation.email,
                            subject=ticket_data["subject"],
                            content=ticket_data["content"],
                            tags=["ai-escalated", "phone-call"]
                        )
                        
                        logger.info(f"Ticket created successfully", extra={"call_sid": call_sid})
                        
                        # Respond to customer with escalation message
                        escalation_message = f"Thank you for providing your email. I'll pass this on to our expert support team. They'll follow up shortly at {conversation.email}. Have a great day!"
                        
                        # Update conversation state
                        conversation.state = CallState.COMPLETED
                        conversation.transcript.append(("AI", escalation_message))
                        
                        # Close Deepgram connection
                        await AudioBridge.close_connection(call_sid)
                        
                        # Clean up transcript callback
                        if call_sid in transcript_callbacks:
                            del transcript_callbacks[call_sid]
                        
                        try:
                            return await TwilioService.create_hangup_response_with_tts(escalation_message)
                        except Exception as e:
                            logger.error(f"Error creating TTS response, falling back to Twilio TTS: {str(e)}", exc_info=True)
                            return TwilioService.create_hangup_response(escalation_message)
                    except Exception as e:
                        logger.error(f"Error creating ticket: {str(e)}", extra={"call_sid": call_sid}, exc_info=True)
                        
                        # Respond to customer with error message
                        error_message = "I'm sorry, but there was an issue creating a support ticket. Please try contacting our support team directly."
                        
                        # Update conversation state
                        conversation.state = CallState.ERROR
                        conversation.transcript.append(("AI", error_message))
                        
                        # Close Deepgram connection
                        await AudioBridge.close_connection(call_sid)
                        
                        # Clean up transcript callback
                        if call_sid in transcript_callbacks:
                            del transcript_callbacks[call_sid]
                        
                        try:
                            return await TwilioService.create_hangup_response_with_tts(error_message)
                        except Exception as e:
                            logger.error(f"Error creating TTS response, falling back to Twilio TTS: {str(e)}", exc_info=True)
                            return TwilioService.create_hangup_response(error_message)
            else:
                # We don't have a response yet, so we need to process the issue again
                conversation.state = CallState.COLLECTING_ISSUE
                
                try:
                    return await TwilioService.create_response_with_tts(
                        message="Thank you for providing your email. Now, how can I assist you today?",
                        gather_speech=True,
                        action_url="/process_issue"
                    )
                except Exception as e:
                    logger.error(f"Error creating TTS response, falling back to Twilio TTS: {str(e)}", exc_info=True)
                    return TwilioService.create_response(
                        message="Thank you for providing your email. Now, how can I assist you today?",
                        gather_speech=True,
                        action_url="/process_issue"
                    )
        else:
            # We don't have an issue yet, so we need to collect it
            conversation.state = CallState.COLLECTING_ISSUE
            
            try:
                return await TwilioService.create_response_with_tts(
                    message="Thank you for providing your email. How can I assist you today?",
                    gather_speech=True,
                    action_url="/process_issue"
                )
            except Exception as e:
                logger.error(f"Error creating TTS response, falling back to Twilio TTS: {str(e)}", exc_info=True)
                return TwilioService.create_response(
                    message="Thank you for providing your email. How can I assist you today?",
                    gather_speech=True,
                    action_url="/process_issue"
                )
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
        
        # Send an acknowledgment response to the customer while we search for an answer
        acknowledgment_message = f"Okay, let me look for information about {issue.split()[:3]}... Please hold for a moment."
        logger.info(f"Sending acknowledgment: {acknowledgment_message}", extra={"call_sid": call_sid})
        
        # Create a task to process the issue and generate a response
        processing_task = asyncio.create_task(process_customer_issue(call_sid, issue, conversation))
        
        # Return the acknowledgment response immediately
        try:
            return await TwilioService.create_response_with_tts(
                message=acknowledgment_message,
                gather_speech=False,
                action_url="/process_response"
            )
        except Exception as e:
            logger.error(f"Error creating TTS response, falling back to Twilio TTS: {str(e)}", exc_info=True)
            return TwilioService.create_response(
                message=acknowledgment_message,
                gather_speech=False,
                action_url="/process_response"
            )
    except Exception as e:
        logger.error(f"Error processing issue: {str(e)}", extra={"call_sid": call_sid}, exc_info=True)
        
        # Respond to customer with error message
        error_message = "I'm sorry, but there was an error processing your request. Please try again later."
        
        # Update conversation state
        if conversation:
            conversation.state = CallState.ERROR
            conversation.transcript.append(("AI", error_message))
        
        # Close Deepgram connection
        await AudioBridge.close_connection(call_sid)
        
        # Clean up transcript callback
        if call_sid in transcript_callbacks:
            del transcript_callbacks[call_sid]
        
        try:
            return await TwilioService.create_hangup_response_with_tts(error_message)
        except Exception as e:
            logger.error(f"Error creating TTS response, falling back to Twilio TTS: {str(e)}", exc_info=True)
            return TwilioService.create_hangup_response(error_message)

async def process_customer_issue(call_sid: str, issue: str, conversation):
    """Process the customer's issue in the background."""
    try:
        # Search Kayako KB for relevant articles
        logger.info(f"Searching Kayako KB for: {issue}", extra={"call_sid": call_sid})
        articles = await KayakoService.search_knowledge_base(issue, limit=3)
        
        if articles:
            # Found relevant articles
            logger.info(f"Found {len(articles)} relevant articles", extra={"call_sid": call_sid})
            
            # Get the full article content for each article
            full_articles = []
            for article in articles:
                article_id = article.get("id")
                if article_id:
                    try:
                        full_article = await KayakoService.get_article_content(article_id)
                        full_articles.append(full_article)
                    except Exception as e:
                        logger.error(f"Error getting article content: {str(e)}", extra={"call_sid": call_sid}, exc_info=True)
                        full_articles.append(article)  # Use the original article if we can't get the full content
                else:
                    full_articles.append(article)  # Use the original article if there's no ID
            
            # Generate a response using OpenAI
            logger.info(f"Generating response with OpenAI", extra={"call_sid": call_sid})
            response_data = await OpenAIService.generate_response(
                query=issue,
                articles=full_articles,
                conversation_history=conversation.transcript
            )
            
            response_message = response_data["text"]
            answer_found = response_data["answer_found"]
            
            # Update conversation transcript
            conversation.transcript.append(("AI", response_message))
            
            # Store the processing result
            processing_results[call_sid] = {
                "response_message": response_message,
                "answer_found": answer_found,
                "has_email": conversation.email is not None
            }
            
            logger.info(f"Processing completed for call {call_sid}", extra={"call_sid": call_sid})
        else:
            # No relevant articles found
            logger.info(f"No relevant articles found", extra={"call_sid": call_sid})
            
            # Store the processing result
            processing_results[call_sid] = {
                "response_message": "I couldn't find any information about that in our knowledge base. Let me collect your email so we can have a support agent follow up with you.",
                "answer_found": False,
                "has_email": conversation.email is not None
            }
    except Exception as e:
        logger.error(f"Error in background processing: {str(e)}", extra={"call_sid": call_sid}, exc_info=True)
        
        # Store the error result
        processing_results[call_sid] = {
            "response_message": "I'm sorry, but there was an error processing your request. Please try again later.",
            "answer_found": False,
            "has_email": conversation.email is not None,
            "error": str(e)
        }

@app.post("/process_response")
async def process_response(request: Request):
    """Process the response after acknowledgment."""
    form_data = await request.form()
    call_sid = form_data["CallSid"]
    
    logger.info(f"Processing response", extra={"call_sid": call_sid})
    
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
        # Wait for processing to complete with a timeout
        max_wait_time = 10  # seconds
        wait_time = 0
        wait_interval = 0.5  # seconds
        
        while call_sid not in processing_results and wait_time < max_wait_time:
            await asyncio.sleep(wait_interval)
            wait_time += wait_interval
        
        if call_sid not in processing_results:
            logger.warning(f"Processing timeout for call {call_sid}", extra={"call_sid": call_sid})
            # Provide a fallback response
            return await handle_email_collection(call_sid, conversation)
        
        # Get the processing result
        result = processing_results[call_sid]
        response_message = result["response_message"]
        answer_found = result["answer_found"]
        has_email = result["has_email"]
        
        # Clean up the processing result
        del processing_results[call_sid]
        
        if answer_found:
            # If an answer was found, check if we need to collect email
            if has_email:
                # We already have the email, so we can end the call
                conversation.state = CallState.COMPLETED
                
                # Close Deepgram connection
                await AudioBridge.close_connection(call_sid)
                
                # Clean up transcript callback
                if call_sid in transcript_callbacks:
                    del transcript_callbacks[call_sid]
                
                try:
                    return await TwilioService.create_hangup_response_with_tts(
                        f"{response_message} Thank you for calling Kayako Support. Have a great day!"
                    )
                except Exception as e:
                    logger.error(f"Error creating TTS response, falling back to Twilio TTS: {str(e)}", exc_info=True)
                    return TwilioService.create_hangup_response(
                        f"{response_message} Thank you for calling Kayako Support. Have a great day!"
                    )
            else:
                # We need to collect email
                conversation.state = CallState.COLLECTING_EMAIL
                
                try:
                    return await TwilioService.create_response_with_tts(
                        message=f"{response_message} To complete this call, could you please provide your email address?",
                        gather_speech=True,
                        action_url="/process_email"
                    )
                except Exception as e:
                    logger.error(f"Error creating TTS response, falling back to Twilio TTS: {str(e)}", exc_info=True)
                    return TwilioService.create_response(
                        message=f"{response_message} To complete this call, could you please provide your email address?",
                        gather_speech=True,
                        action_url="/process_email"
                    )
        else:
            # No answer found, handle email collection or ticket creation
            return await handle_email_collection(call_sid, conversation)
    except Exception as e:
        logger.error(f"Error processing response: {str(e)}", extra={"call_sid": call_sid}, exc_info=True)
        
        # Respond to customer with error message
        error_message = "I'm sorry, but there was an error processing your request. Please try again later."
        
        # Update conversation state
        conversation.state = CallState.ERROR
        conversation.transcript.append(("AI", error_message))
        
        # Close Deepgram connection
        await AudioBridge.close_connection(call_sid)
        
        # Clean up transcript callback
        if call_sid in transcript_callbacks:
            del transcript_callbacks[call_sid]
        
        try:
            return await TwilioService.create_hangup_response_with_tts(error_message)
        except Exception as e:
            logger.error(f"Error creating TTS response, falling back to Twilio TTS: {str(e)}", exc_info=True)
            return TwilioService.create_hangup_response(error_message)

async def handle_email_collection(call_sid: str, conversation):
    """Handle email collection or ticket creation."""
    if conversation.email is None:
        # We need to collect email
        conversation.state = CallState.COLLECTING_EMAIL
        
        try:
            return await TwilioService.create_response_with_tts(
                message="I'll need to create a support ticket for this. Could you please provide your email address?",
                gather_speech=True,
                action_url="/process_email"
            )
        except Exception as e:
            logger.error(f"Error creating TTS response, falling back to Twilio TTS: {str(e)}", exc_info=True)
            return TwilioService.create_response(
                message="I'll need to create a support ticket for this. Could you please provide your email address?",
                gather_speech=True,
                action_url="/process_email"
            )
    else:
        # We already have the email, so we can create a ticket and end the call
        conversation.state = CallState.PROCESSING
        
        # Generate ticket summary
        ticket_data = await OpenAIService.create_ticket_summary(conversation.transcript)
        
        # Create ticket in Kayako
        try:
            ticket = await KayakoService.create_ticket(
                email=conversation.email,
                subject=ticket_data["subject"],
                content=ticket_data["content"],
                tags=["ai-escalated", "phone-call", "no-kb-match"]
            )
            
            logger.info(f"Ticket created successfully", extra={"call_sid": call_sid})
            
            # Respond to customer with escalation message
            escalation_message = f"I'll pass this on to our expert support team. They'll follow up shortly at {conversation.email}. Have a great day!"
            
            # Update conversation state
            conversation.state = CallState.COMPLETED
            conversation.transcript.append(("AI", escalation_message))
            
            # Close Deepgram connection
            await AudioBridge.close_connection(call_sid)
            
            # Clean up transcript callback
            if call_sid in transcript_callbacks:
                del transcript_callbacks[call_sid]
            
            try:
                return await TwilioService.create_hangup_response_with_tts(escalation_message)
            except Exception as e:
                logger.error(f"Error creating TTS response, falling back to Twilio TTS: {str(e)}", exc_info=True)
                return TwilioService.create_hangup_response(escalation_message)
        except Exception as e:
            logger.error(f"Error creating ticket: {str(e)}", extra={"call_sid": call_sid}, exc_info=True)
            
            # Respond to customer with error message
            error_message = "I'm sorry, but there was an issue creating a support ticket. Please try contacting our support team directly."
            
            # Update conversation state
            conversation.state = CallState.ERROR
            conversation.transcript.append(("AI", error_message))
            
            # Close Deepgram connection
            await AudioBridge.close_connection(call_sid)
            
            # Clean up transcript callback
            if call_sid in transcript_callbacks:
                del transcript_callbacks[call_sid]
            
            try:
                return await TwilioService.create_hangup_response_with_tts(error_message)
            except Exception as e:
                logger.error(f"Error creating TTS response, falling back to Twilio TTS: {str(e)}", exc_info=True)
                return TwilioService.create_hangup_response(error_message)

@app.get("/audio/{filename}")
async def get_audio_file(filename: str):
    """Serve audio files generated by Deepgram TTS."""
    # Construct the full path to the audio file
    file_path = os.path.join(gettempdir(), filename)
    
    # Check if the file exists
    if not os.path.exists(file_path):
        logger.error(f"Audio file not found: {file_path}")
        return Response(status_code=404)
    
    # Return the file
    return FileResponse(
        path=file_path,
        media_type="audio/mpeg",
        filename=filename
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
