# kayako-ai-call-assistant

An AI-powered phone assistant for Kayako support using Twilio, Deepgram, and OpenAI.

## Overview

This project implements an AI-powered call assistant for Kayako that:

- Answers incoming customer calls
- Retrieves answers from the Kayako knowledge base
- Uses OpenAI to generate natural, contextual responses
- Responds in real-time if an answer is found
- Escalates to a human agent and creates a Kayako ticket if no answer is found

## Setup

1. Install dependencies:

```bash
pip install -r requirements.txt
```

2. Set up environment variables in `.env`:

```
DEEPGRAM_API_KEY=your-deepgram-key
OPENAI_API_KEY=your-openai-key
TWILIO_AUTH_TOKEN=your-twilio-auth-token
KAYAKO_EMAIL=your-kayako-email
KAYAKO_PASSWORD=your-kayako-password
KAYAKO_URL=your-kayako-url
```

3. Run the application:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

4. Expose your local server with zrok:

```bash
zrok share public localhost:8000
```

5. Configure Twilio to use your zrok URL as the webhook for incoming calls.

## Testing

### Testing Deepgram Integration

To test the Deepgram integration:

```bash
python test_deepgram.py
```

### Testing Kayako Integration

To test the Kayako integration:

```bash
python test_kayako.py
```

### Testing OpenAI Integration

To test the OpenAI integration:

```bash
python test_openai.py
```

## Project Structure

- `app/`: Main application code
  - `main.py`: FastAPI application with route handlers
  - `services/`: Service layer for external integrations
    - `twilio_service.py`: Twilio integration
    - `deepgram_service.py`: Deepgram STT/TTS integration
    - `audio_bridge.py`: Bridge between Twilio and Deepgram
    - `kayako_service.py`: Kayako KB search and ticket creation
    - `openai_service.py`: OpenAI response generation
  - `models/`: Data models
  - `core/`: Core functionality (config, logging)
- `documentation/`: Project documentation
- `test_*.py`: Test scripts for various integrations

## Current Status

- Basic FastAPI application structure is set up
- Twilio integration for call handling is implemented
- Deepgram integration for STT and TTS is implemented
- Kayako integration for KB search and ticket creation is implemented
- OpenAI integration for response generation is implemented
- Basic conversation flow is implemented
- Ticket creation for escalation is implemented

## Call Flow

1. Customer calls the Twilio number
2. AI assistant answers and asks for email
3. Customer provides email
4. AI assistant asks how it can help
5. Customer describes their issue
6. AI searches Kayako KB for relevant articles
7. If relevant articles are found:
   - AI uses OpenAI to generate a response based on the articles
   - If the response is satisfactory, AI provides it to the customer
   - If the response is not satisfactory, AI creates a ticket and escalates
8. If no relevant articles are found:
   - AI creates a ticket with the customer's issue
   - AI informs the customer that a human agent will follow up

## Next Steps

- Implement email validation and confirmation
- Enhance conversation flow with clarification questions
- Optimize response generation with better prompts
- Add more robust error handling
- Implement comprehensive testing
