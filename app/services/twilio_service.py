from twilio.twiml.voice_response import VoiceResponse
from fastapi.responses import Response
from app.models.call import Conversation, CallState, CallResponse

class TwilioService:
    @staticmethod
    def create_response(message: str, gather_speech: bool = False, action_url: str | None = None) -> Response:
        """Create a TwiML response with optional speech gathering."""
        resp = VoiceResponse()
        resp.say(message)
        
        if gather_speech:
            if not action_url:
                raise ValueError("action_url is required when gather_speech is True")
            resp.gather(input="speech", action=action_url, method="POST")
            
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