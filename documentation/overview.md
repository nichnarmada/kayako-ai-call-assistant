# Kayako AI Call Assistant - Implementation Guide

This document outlines the steps and code to build an AI-powered call assistant for Kayako, as per the assignment requirements. It uses **Twilio** for call handling, **Deepgram** for real-time speech-to-text (STT) and text-to-speech (TTS), and **OpenAI** for response generation (since the company provides an OpenAI API key).

**Current Date**: February 24, 2025

---

## Overview

### Goal

Create an AI assistant that:

- Answers incoming customer calls.
- Retrieves answers from the Kayako knowledge base (KB).
- Responds in real-time if an answer is found.
- Escalates to a human agent and creates a Kayako ticket if no answer is found.

### Components

1. **Twilio**: Connects phone calls to the AI system.
2. **Deepgram**: Handles STT (speech → text) and TTS (text → speech) in real time.
3. **OpenAI**: Processes queries and generates responses using the company-provided API key.
4. **Web Server**: Manages call flow, integrates all services, and tracks state.
5. **Kayako API**: Searches the KB and creates tickets.

---

## Prerequisites

- **Twilio Account**: Sign up at [twilio.com](https://www.twilio.com), get a phone number.
- **Deepgram API Key**: Register at [deepgram.com](https://deepgram.com) for STT/TTS access.
- **OpenAI API Key**: Provided by your company.
- **Kayako Test Instance**: Use `https://doug-test.kayako.com`, `anna.kim@trilogy.com`, `Kayakokayako1?`.
- **Python**: Version 3.9+ recommended.
- **zrok**: For exposing local server to the internet ([zrok.io](https://zrok.io)).

---

## Setup Steps

### 1. Install Dependencies

Run this in your terminal to install required Python packages:

```bash
pip install fastapi uvicorn python-multipart twilio websockets aiohttp requests openai httpx
```

### 2. Configure Twilio

- Log into Twilio, buy a phone number.
- Set the webhook URL for incoming calls to your server (e.g., `https://your-zrok-url.share.zrok.io/webhook`).
- Enable speech input in Twilio's settings (Voice → TwiML Apps if needed).

### 3. Expose Local Server with zrok

- Download and install zrok from [zrok.io](https://zrok.io).
- Run: `zrok share public localhost:8000` to get a public URL.
- Update Twilio's webhook with this URL.

### 4. Set Environment Variables

Store API keys securely:

```bash
export DEEPGRAM_API_KEY="your-deepgram-key"
export OPENAI_API_KEY="your-company-openai-key"
export KAYAKO_API_KEY="your-kayako-key"  # If provided, else use test instance auth
```

---

## Code Implementation

Our implementation uses FastAPI with a middleware to handle zrok's interstitial page. The main components include:

1. **FastAPI Application**: Handles HTTP requests and WebSocket connections
2. **Twilio Service**: Manages call flow and TwiML responses
3. **Conversation Model**: Tracks call state and conversation history
4. **Middleware**: Handles zrok interstitial pages automatically

The application is structured with proper separation of concerns:

- `app/main.py`: Main FastAPI application with route handlers
- `app/services/`: Service layer for external integrations
- `app/models/`: Data models for the application
- `app/core/`: Core functionality like configuration and logging

---

## Notes and To-Do List

### Setup Tasks

- [x] Sign up for Twilio and get a phone number.
- [x] Obtain a Deepgram API key and test STT/TTS WebSockets.
- [x] Verify OpenAI API key works with `gpt-4o` or adjust model as per company policy.
- [ ] Test Kayako API with provided credentials
- [x] Install zrok and expose your server.

### Code Adjustments

- [ ] Replace Twilio's `SpeechResult` with Deepgram STT WebSocket calls:
  - Stream audio from Twilio to Deepgram using `websockets`.
- [ ] Integrate Deepgram TTS:
  - Convert `resp.say()` to play Deepgram-generated audio (e.g., save to file, use Twilio `<Play>`).
- [ ] Add error handling:
  - Handle empty speech input (e.g., "Sorry, I didn't catch that").
  - Retry failed API calls.
- [ ] Confirm Kayako API authentication:
  - Replace `KAYAKO_API_KEY` with correct auth method if needed (e.g., Basic Auth).

### Testing

- [ ] Add sample KB articles to Kayako test instance (e.g., "How to reset password").
- [ ] Call Twilio number and test:
  - Email collection works.
  - Simple query (e.g., "I forgot my password") → gets answer.
  - Complex query (e.g., "Custom API help") → escalates and creates ticket.
- [ ] Check Kayako test instance for tickets with transcripts.

---

## How It Works

1. **FastAPI**: Provides modern, async web framework with WebSocket support.
2. **Twilio**: Customer calls → triggers `/webhook` → asks for email.
3. **Deepgram STT**: Real-time transcription via WebSocket connection.
4. **OpenAI**: Processes query, searches Kayako KB, generates response.
5. **Deepgram TTS**: Converts response to audio via WebSocket.
6. **Twilio**: Plays response, ends call.
7. **Kayako**: Creates ticket if escalated.

---

## Next Steps

- [ ] Fully integrate Deepgram WebSockets for STT and TTS (current code uses Twilio's placeholder).
- [ ] Optimize latency (aim for <1s response time).
- [ ] Add email confirmation step (e.g., "Did I get that right?").
- [ ] Tag tickets in Kayako for easier agent triage.

This should get you started! Update this file as you progress.

```

```
