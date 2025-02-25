import json
from typing import Dict, List, Optional, Any
from openai import AsyncOpenAI
from app.core.config import get_settings
from app.core.logger import logger

class OpenAIService:
    """Service for interacting with OpenAI's API."""
    
    # Store the client for reuse
    _client: Optional[AsyncOpenAI] = None
    
    @classmethod
    def get_client(cls) -> AsyncOpenAI:
        """
        Get or create an OpenAI client.
        
        Returns:
            AsyncOpenAI client
        """
        if cls._client is None:
            settings = get_settings()
            # Initialize with only the required parameters
            cls._client = AsyncOpenAI(
                api_key=settings.OPENAI_API_KEY,
                # Don't include any other parameters that might cause issues
            )
        return cls._client
    
    @classmethod
    async def generate_response(cls, 
                               query: str, 
                               articles: List[Dict[str, Any]], 
                               conversation_history: List[tuple] = None) -> Dict[str, Any]:
        """
        Generate a response using OpenAI based on the query and knowledge base articles.
        
        Args:
            query: User's query
            articles: List of knowledge base articles
            conversation_history: List of (speaker, text) tuples representing the conversation history
            
        Returns:
            Dictionary with response text and metadata
        """
        client = cls.get_client()
        settings = get_settings()
        
        # Format articles for the prompt
        formatted_articles = []
        for i, article in enumerate(articles):
            title = article.get("title", "Untitled Article")
            content = ""
            
            # Extract content from the article
            contents = article.get("contents", [])
            if contents:
                for content_item in contents:
                    if content_item.get("locale", {}).get("id") == 2:  # English content
                        content = content_item.get("text", "")
                        break
            
            formatted_articles.append(f"Article {i+1}: {title}\n{content}")
        
        articles_text = "\n\n".join(formatted_articles)
        
        # Format conversation history
        conversation_context = ""
        if conversation_history:
            conversation_context = "\n".join([f"{speaker}: {text}" for speaker, text in conversation_history])
        
        # Create the prompt
        system_prompt = """
        You are an AI assistant for Kayako customer support. Your job is to help customers by providing accurate information from the knowledge base.
        
        Follow these guidelines:
        1. If the knowledge base articles contain information relevant to the query, provide a helpful, concise response based on that information.
        2. If the articles don't contain relevant information, indicate that you don't have the answer and that a human agent will need to follow up.
        3. Be conversational and friendly, but professional.
        4. Keep responses concise and to the point.
        5. Don't make up information that isn't in the knowledge base articles.
        
        Respond in a natural, conversational way as if you're speaking to the customer on a phone call.
        """
        
        user_prompt = f"""
        Customer Query: {query}
        
        Previous Conversation:
        {conversation_context}
        
        Knowledge Base Articles:
        {articles_text}
        
        Based on the above information, please provide a response to the customer's query.
        """
        
        logger.info(f"API request: Generating OpenAI response for query: '{query}'")
        try:
            response = await client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7,
                max_tokens=500
            )
            
            response_text = response.choices[0].message.content.strip()
            
            # Determine if the response indicates an answer was found
            answer_found = "human agent" not in response_text.lower() and "follow up" not in response_text.lower()
            
            logger.info(f"API response: Generated response: {response_text[:100]}...")
            return {
                "text": response_text,
                "answer_found": answer_found,
                "model": settings.OPENAI_MODEL,
                "usage": {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens
                }
            }
        except Exception as e:
            logger.error(f"API error: OpenAI response generation failed: {str(e)}")
            return {
                "text": "I'm sorry, but I'm having trouble generating a response right now. Let me connect you with a human agent who can help.",
                "answer_found": False,
                "error": str(e)
            }
    
    @classmethod
    async def create_ticket_summary(cls, conversation_history: List[tuple]) -> Dict[str, str]:
        """
        Generate a summary of the conversation for a ticket.
        
        Args:
            conversation_history: List of (speaker, text) tuples representing the conversation history
            
        Returns:
            Dictionary with subject and content for the ticket
        """
        client = cls.get_client()
        settings = get_settings()
        
        # Format conversation history
        conversation_text = "\n".join([f"{speaker}: {text}" for speaker, text in conversation_history])
        
        system_prompt = """
        You are an AI assistant for Kayako customer support. Your job is to summarize customer conversations for support tickets.
        
        Follow these guidelines:
        1. Create a concise subject line that captures the main issue.
        2. Summarize the key points of the conversation.
        3. Highlight any specific questions or requests from the customer.
        4. Be objective and factual.
        
        Format your response as:
        Subject: [Concise subject line]
        
        [Summary of the conversation and key points]
        """
        
        user_prompt = f"""
        Conversation Transcript:
        {conversation_text}
        
        Please summarize this conversation for a support ticket.
        """
        
        logger.info("API request: Generating ticket summary with OpenAI")
        try:
            response = await client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.5,
                max_tokens=300
            )
            
            summary_text = response.choices[0].message.content.strip()
            
            # Extract subject and content
            parts = summary_text.split("\n\n", 1)
            subject = parts[0].replace("Subject:", "").strip()
            content = parts[1] if len(parts) > 1 else summary_text
            
            logger.info(f"API response: Generated ticket summary with subject: '{subject}'")
            return {
                "subject": subject,
                "content": content
            }
        except Exception as e:
            logger.error(f"API error: Ticket summary generation failed: {str(e)}")
            return {
                "subject": "Customer Support Request",
                "content": f"Conversation transcript:\n{conversation_text}\n\nNote: This ticket was automatically created by the AI assistant."
            } 