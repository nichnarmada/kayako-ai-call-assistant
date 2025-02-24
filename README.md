# kayako-ai-call-assistant

An AI-powered phone assistant for Kayako support using Twilio, Deepgram, and OpenAI.

## Overview

This project implements an AI-powered call assistant for Kayako that:

- Answers incoming customer calls
- Retrieves answers from the Kayako knowledge base
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
KAYAKO_API_KEY=your-kayako-key  # If provided
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

## Testing Deepgram Integration

To test the Deepgram integration:

1. Make sure your `.env` file has a valid `DEEPGRAM_API_KEY`.
2. Run the Deepgram test script:

```bash
python test_deepgram.py
```

This will test the Deepgram TTS functionality and generate a sample audio file. If you have a `test_audio.wav` file, it will also test the STT functionality.

## Project Structure

- `app/`: Main application code
  - `main.py`: FastAPI application with route handlers
  - `services/`: Service layer for external integrations
    - `twilio_service.py`: Twilio integration
    - `deepgram_service.py`: Deepgram STT/TTS integration
    - `audio_bridge.py`: Bridge between Twilio and Deepgram
  - `models/`: Data models
  - `core/`: Core functionality (config, logging)
- `documentation/`: Project documentation
- `test_deepgram.py`: Script to test Deepgram integration

## Current Status

- Basic FastAPI application structure is set up
- Twilio integration for call handling is implemented
- Deepgram integration for STT and TTS is implemented
- Basic conversation flow is implemented
- TODO: Implement Kayako KB search and OpenAI integration
