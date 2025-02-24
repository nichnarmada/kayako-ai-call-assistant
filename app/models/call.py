from pydantic import BaseModel, EmailStr
from typing import List, Tuple, Optional
from enum import Enum

class CallState(Enum):
    INIT = "init"
    COLLECTING_EMAIL = "collecting_email"
    CONFIRMING_EMAIL = "confirming_email"
    COLLECTING_ISSUE = "collecting_issue"
    PROCESSING = "processing"
    RESPONDING = "responding"
    COMPLETED = "completed"
    ERROR = "error"

class Conversation(BaseModel):
    call_sid: str
    email: Optional[EmailStr] = None
    state: CallState = CallState.INIT
    transcript: List[Tuple[str, str]] = []  # List of (speaker, text) tuples
    
class CallResponse(BaseModel):
    success: bool
    message: str
    next_action: Optional[str] = None 