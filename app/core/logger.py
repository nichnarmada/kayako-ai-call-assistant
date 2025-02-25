import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler
import json
from datetime import datetime

# Create logs directory if it doesn't exist
logs_dir = Path("logs")
logs_dir.mkdir(exist_ok=True)

class ConversationFormatter(logging.Formatter):
    """Formatter that focuses on conversation flow and API interactions"""
    
    def format(self, record):
        # Skip debug messages
        if record.levelno < logging.INFO:
            return ""
            
        # Get the message
        message = record.getMessage()
        
        # Format based on content
        if "New call received" in message:
            return f"\n🔵 NEW CALL: {getattr(record, 'call_sid', 'Unknown')}"
        elif "Conversation initialized" in message:
            return "🔵 Call initialized"
        elif "Processing issue" in message:
            return f"👤 CUSTOMER: {record.args.get('issue', '')}" if hasattr(record, 'args') and isinstance(record.args, dict) else message
        elif "Processing email" in message:
            return f"👤 CUSTOMER EMAIL: {record.args.get('email', '')}" if hasattr(record, 'args') and isinstance(record.args, dict) else message
        elif "Sending acknowledgment" in message:
            acknowledgment = message.replace("Sending acknowledgment:", "").strip()
            return f"🤖 AI ACKNOWLEDGMENT: {acknowledgment}"
        elif "STT final transcript" in message:
            transcript = message.replace("STT final transcript:", "").strip()
            return f"🎤 CUSTOMER (STT): {transcript}"
        elif "STT interim transcript" in message:
            transcript = message.replace("STT interim transcript:", "").strip()
            return f"🎤 CUSTOMER (STT interim): {transcript}"
        elif "Searching Kayako KB" in message:
            return f"🔍 SEARCHING KB: {record.args.get('issue', '')}" if hasattr(record, 'args') and isinstance(record.args, dict) else "🔍 Searching knowledge base..."
        elif "Found" in message and "relevant articles" in message:
            return f"📚 FOUND ARTICLES: {record.args.get('len', '0')} articles" if hasattr(record, 'args') and isinstance(record.args, dict) else message
        elif "Generating response with OpenAI" in message:
            return "🤖 Generating AI response..."
        elif "Generated response" in message:
            return f"🤖 AI RESPONSE: {message.split('Generated response:')[1].strip()}" if ":" in message else message
        elif "Processing completed" in message:
            return f"✅ Processing completed for call {getattr(record, 'call_sid', 'Unknown')}"
        elif "Answer found" in message:
            return "✅ Answer found, responding to customer"
        elif "No answer found" in message or "No relevant articles found" in message:
            return "❌ No answer found, creating ticket"
        elif "Ticket created successfully" in message:
            return "🎫 Ticket created successfully"
        elif "Call completed" in message or "WebSocket disconnected" in message:
            return "👋 Call ended"
        elif "Error" in message.lower():
            return f"❗ ERROR: {message}"
        elif "API request" in message:
            return f"🌐 API REQUEST: {message.split('API request')[1].strip()}" if ":" in message else message
        elif "API response" in message:
            return f"🌐 API RESPONSE: {message.split('API response')[1].strip()}" if ":" in message else message
        else:
            # For other messages, just return the message without any formatting
            return message

class JsonFormatter(logging.Formatter):
    """Formatter that outputs logs in JSON format for file logging"""
    
    def format(self, record):
        log_obj = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
        }
        
        if hasattr(record, 'call_sid'):
            log_obj["call_sid"] = record.call_sid
            
        # Add transcript type if available
        if hasattr(record, 'transcript_type'):
            log_obj["transcript_type"] = record.transcript_type
            
            # Extract the transcript text from the message
            if "STT final transcript" in record.getMessage():
                log_obj["transcript"] = record.getMessage().replace("STT final transcript:", "").strip()
            elif "STT interim transcript" in record.getMessage():
                log_obj["transcript"] = record.getMessage().replace("STT interim transcript:", "").strip()
            
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)
            
        return json.dumps(log_obj)

def setup_logger(name: str = "kayako_assistant") -> logging.Logger:
    """Set up and configure logger"""
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    
    # Prevent duplicate handlers
    if logger.handlers:
        return logger
        
    # Console handler with conversation-focused formatter
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(ConversationFormatter())
    logger.addHandler(console_handler)
    
    # File handler with detailed JSON formatter
    file_handler = RotatingFileHandler(
        logs_dir / "app.log",
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5
    )
    file_handler.setFormatter(JsonFormatter())
    logger.addHandler(file_handler)
    
    return logger

# Create default logger instance
logger = setup_logger() 