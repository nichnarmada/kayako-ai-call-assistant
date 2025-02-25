import json
from typing import Dict, List, Optional, Any
from openai import AsyncOpenAI
from app.core.config import get_settings
from app.core.logger import logger

class OpenAIService:
    """Service for interacting with OpenAI's API."""
    
    # Store the client for reuse
    _client: Optional[AsyncOpenAI] = None
    
    # Add content cache for article content
    _content_cache: Dict[int, str] = {}
    
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
        logger.info(f"Processing {len(articles)} articles for response generation")
        
        for i, article in enumerate(articles):
            # Extract title
            title = ""
            
            # Get title from titles array
            titles = article.get("titles", [])
            for title_obj in titles:
                if isinstance(title_obj, dict):
                    # Try to get the locale
                    locale = title_obj.get("locale", {})
                    if isinstance(locale, dict) and locale.get("id") == 2:  # English
                        title = title_obj.get("translation", "")
                        break
                    # If locale is not a dict or doesn't have id, try to get translation directly
                    elif "translation" in title_obj:
                        title = title_obj.get("translation", "")
                        break
            
            # If we couldn't find a title in the titles array, try the title field directly
            if not title and "title" in article:
                title = article["title"]
            
            # If we still don't have a title, check for slugs
            if not title and "slugs" in article and article["slugs"]:
                for slug in article["slugs"]:
                    if isinstance(slug, dict) and "translation" in slug:
                        # Extract a readable title from the slug
                        slug_text = slug["translation"]
                        # Remove the ID prefix if present (e.g., "54-changing-the-name..." -> "changing-the-name...")
                        if "-" in slug_text:
                            slug_text = "-".join(slug_text.split("-")[1:])
                        # Replace hyphens with spaces and capitalize words
                        title = " ".join(word.capitalize() for word in slug_text.split("-"))
                        break
            
            logger.info(f"Article {i+1} title: {title}")
            
            # Get content - using a more thorough approach similar to prepare_article_for_tts
            content = ""
            
            # First check if we have a 'content' field directly
            if "content" in article and article["content"]:
                content = article["content"]
                logger.info(f"Found content in 'content' field for article {i+1}")
            # Then check if we have a 'translation' field (sometimes used for content)
            elif "translation" in article and article["translation"]:
                content = article["translation"]
                logger.info(f"Found content in 'translation' field for article {i+1}")
            
            # If we still don't have content, look for content_id in contents array
            if not content:
                content_id = None
                contents = article.get("contents", [])
                for content_obj in contents:
                    if isinstance(content_obj, dict):
                        # Check if it's a reference to a locale field
                        if content_obj.get("resource_type") == "locale_field" and "id" in content_obj:
                            content_id = content_obj.get("id")
                            logger.info(f"Found content_id {content_id} for article {i+1}")
                            break
                
                # If we found a content ID, try to get it from the cache
                if content_id and hasattr(cls, "_content_cache") and content_id in cls._content_cache:
                    content = cls._content_cache[content_id]
                    logger.info(f"Retrieved content from cache for article {i+1}")
            
            # If we still don't have content, look for it in the article structure
            if not content:
                # Check if this is a full article with locale_field content already fetched
                for key, value in article.items():
                    if isinstance(value, str) and len(value) > 100:  # Likely content
                        content = value
                        logger.info(f"Found content in '{key}' field for article {i+1}")
                        break
            
            # Clean up the content for better readability
            if content:
                # Remove HTML tags
                import re
                content = re.sub(r'<[^>]+>', ' ', content)
                # Replace multiple spaces with a single space
                content = re.sub(r'\s+', ' ', content)
                # Replace special characters
                content = content.replace('&nbsp;', ' ')
                content = content.replace('&amp;', 'and')
                content = content.replace('&lt;', 'less than')
                content = content.replace('&gt;', 'greater than')
                
                logger.info(f"Article {i+1} content length: {len(content)} characters")
                if len(content) > 100:
                    logger.info(f"Article {i+1} content preview: {content[:100]}...")
                else:
                    logger.info(f"Article {i+1} content is too short: {content}")
            else:
                logger.warning(f"No content found for article {i+1}")
            
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
        6. If you find relevant information in the articles, NEVER say you don't have the information or that a human agent needs to follow up.
        7. Pay close attention to the specific question being asked and extract the most relevant information from the articles.
        8. If an article mentions a process or steps related to the query, include that information in your response.
        9. If the article title seems relevant to the query but the content doesn't directly address it, still try to provide helpful information based on what is available.
        
        Respond in a natural, conversational way as if you're speaking to the customer on a phone call.
        """
        
        user_prompt = f"""
        Customer Query: {query}
        
        Previous Conversation:
        {conversation_context}
        
        Knowledge Base Articles:
        {articles_text}
        
        Based on the above information, please provide a response to the customer's query. 
        If the articles contain the information needed to answer the query, provide that information directly.
        Only say you don't have the information if the articles truly don't contain relevant information.
        Focus specifically on answering the customer's question about {query.lower()}.
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
            
            # Improved logic to determine if the response indicates an answer was found
            negative_phrases = [
                "don't have the specific steps",
                "don't have the information",
                "couldn't find",
                "human agent will follow up",
                "human agent will need to follow up",
                "need to connect you with a human agent",
                "I don't have access to",
                "I don't have the details",
                "there isn't any specific information",
                "I don't have specific information",
                "I don't have the specific information",
                "doesn't contain information",
                "doesn't provide information",
                "no specific information",
                "no information about",
                "doesn't mention how to"
            ]
            
            answer_found = True  # Assume answer is found by default
            for phrase in negative_phrases:
                if phrase in response_text.lower():
                    answer_found = False
                    break
            
            # If the response indicates no answer was found but the article titles seem relevant,
            # we'll force the model to try again with a more direct prompt
            if not answer_found:
                relevant_titles = []
                for article in articles:
                    # Extract title
                    title = ""
                    titles = article.get("titles", [])
                    for title_obj in titles:
                        if isinstance(title_obj, dict) and "translation" in title_obj:
                            title = title_obj.get("translation", "")
                            break
                    if not title and "title" in article:
                        title = article["title"]
                    
                    # Check if title seems relevant to the query
                    if title and any(keyword in title.lower() for keyword in query.lower().split()):
                        relevant_titles.append(title)
                
                if relevant_titles:
                    # Try again with a more direct prompt
                    retry_prompt = f"""
                    Customer Query: {query}
                    
                    I found these relevant articles that might help: {', '.join(relevant_titles)}
                    
                    Knowledge Base Articles:
                    {articles_text}
                    
                    The customer is specifically asking about {query}. Please carefully review the articles again and provide information that would help the customer. 
                    Even if the articles don't have step-by-step instructions, provide any relevant information you can find.
                    Do NOT say you don't have information if there's anything at all in the articles that could help with this query.
                    """
                    
                    retry_response = await client.chat.completions.create(
                        model=settings.OPENAI_MODEL,
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": retry_prompt}
                        ],
                        temperature=0.5,  # Lower temperature for more focused response
                        max_tokens=500
                    )
                    
                    retry_text = retry_response.choices[0].message.content.strip()
                    
                    # Check if the retry response is better
                    retry_has_negative = False
                    for phrase in negative_phrases:
                        if phrase in retry_text.lower():
                            retry_has_negative = True
                            break
                    
                    if not retry_has_negative:
                        response_text = retry_text
                        answer_found = True
            
            logger.info(f"API response: Generated response: {response_text[:100]}... Answer found: {answer_found}")
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
                "content": "Customer had a support request. Please review the conversation history for details."
            }
    
    @classmethod
    async def extract_search_keywords(cls, customer_speech: str) -> Dict[str, Any]:
        """
        Process customer's speech to extract relevant search keywords for Kayako.
        
        Args:
            customer_speech: The raw speech-to-text output from the customer
            
        Returns:
            Dictionary with extracted keywords and metadata
        """
        client = cls.get_client()
        settings = get_settings()
        
        system_prompt = """
        You are an AI assistant for Kayako customer support. Your job is to analyze customer queries and extract the most relevant search keywords for knowledge base searches.
        
        Follow these guidelines:
        1. Identify the core issue or question in the customer's speech.
        2. Extract 2-5 specific keywords or phrases that would be most effective for searching a knowledge base.
        3. Focus on technical terms, product names, error messages, and specific actions.
        4. Ignore filler words, pleasantries, and irrelevant context.
        5. Format the output as a comma-separated list of keywords.
        
        For example:
        - From "Hi, I'm having trouble logging into my account. It keeps saying invalid password even though I'm sure it's correct" → "login issue, invalid password, authentication error"
        - From "I purchased your product yesterday but haven't received any confirmation email yet" → "missing confirmation email, recent purchase"
        """
        
        user_prompt = f"""
        Customer's speech: "{customer_speech}"
        
        Extract the most relevant search keywords from this customer query.
        """
        
        logger.info(f"API request: Extracting search keywords from: '{customer_speech[:50]}...'")
        try:
            response = await client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3,
                max_tokens=100
            )
            
            keywords = response.choices[0].message.content.strip()
            
            logger.info(f"API response: Extracted keywords: '{keywords}'")
            return {
                "keywords": keywords,
                "original_speech": customer_speech,
                "usage": {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens
                }
            }
        except Exception as e:
            logger.error(f"API error: Keyword extraction failed: {str(e)}")
            # If extraction fails, return the original speech as the keyword
            return {
                "keywords": customer_speech,
                "original_speech": customer_speech,
                "error": str(e)
            } 