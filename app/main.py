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
        acknowledgment_message = "Okay, let me look it up for you. Please hold for a moment."
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
        # Extract relevant search keywords from the customer's issue
        logger.info(f"Extracting search keywords from: {issue}", extra={"call_sid": call_sid})
        keyword_result = await OpenAIService.extract_search_keywords(issue)
        search_query = keyword_result.get("keywords", issue)
        
        # Log the original issue and the extracted keywords
        logger.info(f"Original issue: '{issue}'", extra={"call_sid": call_sid})
        logger.info(f"Extracted search query: '{search_query}'", extra={"call_sid": call_sid})
        
        # Search Kayako KB for relevant articles using the extracted keywords
        logger.info(f"Searching knowledge base...", extra={"call_sid": call_sid})
        articles = await KayakoService.search_knowledge_base(search_query, limit=3)
        
        if articles:
            # Found relevant articles
            logger.info(f"Found {len(articles)} relevant articles", extra={"call_sid": call_sid})
            
            # Get the full article content for each article
            full_articles = []
            tts_content = None  # Store TTS content for the top article
            
            for i, article in enumerate(articles):
                article_id = article.get("id")
                if article_id:
                    try:
                        full_article = await KayakoService.get_article_content(article_id)
                        full_articles.append(full_article)
                        
                        # Prepare TTS content for the top article
                        if i == 0 and not tts_content:
                            tts_content = await KayakoService.prepare_article_for_tts(full_article)
                            
                        # Share content cache with OpenAIService
                        for content_obj in full_article.get("contents", []):
                            if isinstance(content_obj, dict) and content_obj.get("resource_type") == "locale_field" and "id" in content_obj:
                                content_id = content_obj.get("id")
                                if content_id in KayakoService._content_cache:
                                    OpenAIService._content_cache[content_id] = KayakoService._content_cache[content_id]
                    except Exception as e:
                        logger.error(f"Error getting article content: {str(e)}", extra={"call_sid": call_sid}, exc_info=True)
                        full_articles.append(article)  # Use the original article if we can't get the full content
                        
                        # Prepare TTS content from the original article if needed
                        if i == 0 and not tts_content:
                            tts_content = await KayakoService.prepare_article_for_tts(article)
                else:
                    full_articles.append(article)  # Use the original article if there's no ID
                    
                    # Prepare TTS content from the original article if needed
                    if i == 0 and not tts_content:
                        tts_content = await KayakoService.prepare_article_for_tts(article)
            
            # Generate a response using OpenAI
            logger.info(f"Generating AI response...", extra={"call_sid": call_sid})
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
                "has_email": conversation.email is not None,
                "tts_content": tts_content  # Include TTS content for article reading
            }
            
            logger.info(f"✅ Processing completed for call {call_sid}", extra={"call_sid": call_sid})
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
    """Process the response to the customer's issue."""
    form_data = await request.form()
    call_sid = form_data["CallSid"]
    
    logger.info(f"Processing response", extra={"call_sid": call_sid})
    
    # Get the processing result
    result = processing_results.get(call_sid)
    if not result:
        logger.error(f"Processing result not found", extra={"call_sid": call_sid})
        try:
            return await TwilioService.create_hangup_response_with_tts(
                "I'm sorry, but there was an error with your call. Please try again."
            )
        except Exception as e:
            logger.error(f"Error creating TTS response, falling back to Twilio TTS: {str(e)}", exc_info=True)
            return TwilioService.create_hangup_response(
                "I'm sorry, but there was an error with your call. Please try again."
            )
    
    # Get the conversation
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
    
    # Get the response message and answer status
    response_message = result.get("response_message", "")
    answer_found = result.get("answer_found", False)
    has_email = result.get("has_email", False)
    tts_content = result.get("tts_content")
    
    # If we found an answer and have TTS content, use the AI-generated response
    if answer_found:
        logger.info(f"Answer found, using AI-generated response", extra={"call_sid": call_sid})
        try:
            return await TwilioService.create_response_with_tts(
                message=response_message,
                gather_speech=True,
                action_url="/handle_followup"
            )
        except Exception as e:
            logger.error(f"Error creating TTS response, falling back to Twilio TTS: {str(e)}", exc_info=True)
            return TwilioService.create_response(
                message=response_message,
                gather_speech=True,
                action_url="/handle_followup"
            )
    else:
        # If we didn't find an answer, ask for the customer's email
        if not has_email:
            logger.info(f"No answer found, asking for email", extra={"call_sid": call_sid})
            try:
                return await TwilioService.create_response_with_tts(
                    message=response_message + " Could you please provide your email address so we can follow up with you?",
                    gather_speech=True,
                    action_url="/collect_email",
                    speech_timeout="auto"
                )
            except Exception as e:
                logger.error(f"Error creating TTS response, falling back to Twilio TTS: {str(e)}", exc_info=True)
                return TwilioService.create_response(
                    message=response_message + " Could you please provide your email address so we can follow up with you?",
                    gather_speech=True,
                    action_url="/collect_email",
                    speech_timeout="auto"
                )
        else:
            # If we already have the email, thank the customer
            logger.info(f"No answer found, but already have email", extra={"call_sid": call_sid})
            try:
                return await TwilioService.create_response_with_tts(
                    message=response_message + f" We already have your email as {conversation.email}. A support agent will follow up with you shortly.",
                    gather_speech=False,
                    action_url="/handle_followup"
                )
            except Exception as e:
                logger.error(f"Error creating TTS response, falling back to Twilio TTS: {str(e)}", exc_info=True)
                return TwilioService.create_response(
                    message=response_message + f" We already have your email as {conversation.email}. A support agent will follow up with you shortly.",
                    gather_speech=False,
                    action_url="/handle_followup"
                )

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

@app.post("/handle_followup")
async def handle_followup(request: Request):
    """Handle follow-up questions from the customer."""
    form_data = await request.form()
    call_sid = form_data["CallSid"]
    
    # Get speech result if available
    speech_result = form_data.get("SpeechResult", "")
    
    logger.info(f"Handling follow-up: {speech_result}", extra={"call_sid": call_sid})
    
    # Get the conversation
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
    
    # Check if the customer wants to end the call
    end_call_phrases = ["goodbye", "bye", "thank you", "thanks", "that's all", "that is all", "end call", "hang up"]
    if any(phrase in speech_result.lower() for phrase in end_call_phrases):
        logger.info(f"Customer ending call", extra={"call_sid": call_sid})
        try:
            return await TwilioService.create_hangup_response_with_tts(
                "Thank you for calling Kayako Support. Have a great day!"
            )
        except Exception as e:
            logger.error(f"Error creating TTS response, falling back to Twilio TTS: {str(e)}", exc_info=True)
            return TwilioService.create_hangup_response(
                "Thank you for calling Kayako Support. Have a great day!"
            )
    
    # If the customer has a follow-up question, process it
    if speech_result:
        # Update conversation transcript
        conversation.transcript.append(("Customer", speech_result))
        
        # Process the follow-up question
        try:
            return await process_issue(request)
        except Exception as e:
            logger.error(f"Error processing follow-up: {str(e)}", extra={"call_sid": call_sid}, exc_info=True)
            try:
                return await TwilioService.create_hangup_response_with_tts(
                    "I'm sorry, but there was an error processing your follow-up question. Please try again later."
                )
            except Exception as e:
                logger.error(f"Error creating TTS response, falling back to Twilio TTS: {str(e)}", exc_info=True)
                return TwilioService.create_hangup_response(
                    "I'm sorry, but there was an error processing your follow-up question. Please try again later."
                )
    else:
        # If no speech was detected, ask if they need anything else
        logger.info(f"No speech detected, asking if customer needs anything else", extra={"call_sid": call_sid})
        try:
            return await TwilioService.create_response_with_tts(
                message="Is there anything else I can help you with today?",
                gather_speech=True,
                action_url="/handle_followup"
            )
        except Exception as e:
            logger.error(f"Error creating TTS response, falling back to Twilio TTS: {str(e)}", exc_info=True)
            return TwilioService.create_response(
                message="Is there anything else I can help you with today?",
                gather_speech=True,
                action_url="/handle_followup"
            )

@app.post("/collect_email")
async def collect_email(request: Request):
    """Collect the customer's email address."""
    form_data = await request.form()
    call_sid = form_data["CallSid"]
    
    # Get speech result if available
    speech_result = form_data.get("SpeechResult", "")
    
    logger.info(f"Collecting email: {speech_result}", extra={"call_sid": call_sid})
    
    # Get the conversation
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
    
    # Extract email from speech result
    email = None
    if speech_result:
        # Simple email extraction - look for something with @ symbol
        import re
        email_match = re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', speech_result)
        if email_match:
            email = email_match.group(0)
    
    if email:
        # Update conversation with email
        conversation.email = email
        conversation.transcript.append(("Customer", f"Email: {email}"))
        
        # Generate ticket summary
        ticket_data = await OpenAIService.create_ticket_summary(conversation.transcript)
        
        # Create ticket in Kayako
        try:
            ticket = await KayakoService.create_ticket(
                email=email,
                subject=ticket_data["subject"],
                content=ticket_data["content"],
                tags=["ai-escalated", "phone-call"]
            )
            
            logger.info(f"Ticket created successfully", extra={"call_sid": call_sid})
            
            # Thank the customer and end the call
            try:
                return await TwilioService.create_hangup_response_with_tts(
                    f"Thank you. I've created a support ticket and our team will follow up with you at {email} shortly. Have a great day!"
                )
            except Exception as e:
                logger.error(f"Error creating TTS response, falling back to Twilio TTS: {str(e)}", exc_info=True)
                return TwilioService.create_hangup_response(
                    f"Thank you. I've created a support ticket and our team will follow up with you at {email} shortly. Have a great day!"
                )
        except Exception as e:
            logger.error(f"Error creating ticket: {str(e)}", extra={"call_sid": call_sid}, exc_info=True)
            try:
                return await TwilioService.create_hangup_response_with_tts(
                    f"I'm sorry, but there was an issue creating a support ticket. Please try contacting our support team directly at support@kayako.com."
                )
            except Exception as e:
                logger.error(f"Error creating TTS response, falling back to Twilio TTS: {str(e)}", exc_info=True)
                return TwilioService.create_hangup_response(
                    f"I'm sorry, but there was an issue creating a support ticket. Please try contacting our support team directly at support@kayako.com."
                )
    else:
        # If no email was detected, ask again
        logger.info(f"No email detected, asking again", extra={"call_sid": call_sid})
        try:
            return await TwilioService.create_response_with_tts(
                message="I'm sorry, I didn't catch your email address. Could you please spell it out for me?",
                gather_speech=True,
                action_url="/collect_email",
                speech_timeout="auto"
            )
        except Exception as e:
            logger.error(f"Error creating TTS response, falling back to Twilio TTS: {str(e)}", exc_info=True)
            return TwilioService.create_response(
                message="I'm sorry, I didn't catch your email address. Could you please spell it out for me?",
                gather_speech=True,
                action_url="/collect_email",
                speech_timeout="auto"
            )

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
