import base64
import httpx
import asyncio
import re
from typing import Dict, List, Optional, Any, Tuple
from app.core.config import get_settings
from app.core.logger import logger

class KayakoService:
    """Service for interacting with Kayako's API."""
    
    # Store the session ID for reuse
    _session_id: Optional[str] = None
    
    # Add caches for content and articles
    _content_cache: Dict[int, str] = {}
    
    @classmethod
    async def authenticate(cls) -> str:
        """
        Authenticate with Kayako API using Basic HTTP Authentication.
        
        Returns:
            Session ID for future requests
        """
        if cls._session_id:
            return cls._session_id
            
        settings = get_settings()
        kayako_url = settings.KAYAKO_URL
        email = settings.KAYAKO_EMAIL
        password = settings.KAYAKO_PASSWORD
        
        # Create the Authorization header
        auth_string = f"{email}:{password}"
        encoded_auth = base64.b64encode(auth_string.encode()).decode()
        headers = {
            "Authorization": f"Basic {encoded_auth}"
        }
        
        # Make authentication request
        logger.info("API request: Authenticating with Kayako API")
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{kayako_url}/api/v1/me.json", headers=headers)
                
                if response.status_code == 200:
                    data = response.json()
                    # Store the session_id for future requests
                    cls._session_id = data.get("session_id")
                    logger.info(f"API response: Authentication successful, session ID obtained")
                    return cls._session_id
                else:
                    logger.error(f"API response: Authentication failed: {response.status_code}")
                    raise Exception(f"Authentication failed: {response.text}")
        except Exception as e:
            logger.error(f"API error: Authentication request failed: {str(e)}")
            raise
    
    @classmethod
    async def get_user_info(cls) -> Dict[str, Any]:
        """
        Get information about the authenticated user.
        
        Returns:
            User information
        """
        # Ensure we have a session ID
        session_id = await cls.authenticate()
        
        settings = get_settings()
        kayako_url = settings.KAYAKO_URL
        
        headers = {
            "X-Session-ID": session_id
        }
        
        logger.info("Getting user information")
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{kayako_url}/api/v1/me.json", 
                    headers=headers
                )
                
                if response.status_code == 200:
                    data = response.json()
                    user_info = data.get("data", {})
                    logger.info(f"Successfully retrieved user information")
                    return user_info
                else:
                    logger.error(f"Failed to get user info: {response.status_code} - {response.text}")
                    return {}
        except Exception as e:
            logger.error(f"Error getting user info: {str(e)}", exc_info=True)
            return {}
    
    @classmethod
    async def get_locale_field_content(cls, content_id: int) -> str:
        """
        Get the content of a locale field by ID with caching.
        
        Args:
            content_id: ID of the locale field to retrieve
            
        Returns:
            Content text
        """
        # Check cache first
        if content_id in cls._content_cache:
            logger.info(f"Retrieved locale field content from cache for ID: {content_id}")
            return cls._content_cache[content_id]
            
        # Ensure we have a session ID
        session_id = await cls.authenticate()
        
        settings = get_settings()
        kayako_url = settings.KAYAKO_URL
        
        headers = {
            "X-Session-ID": session_id
        }
        
        logger.info(f"Getting locale field content for ID: {content_id}")
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{kayako_url}/api/v1/locale/fields/{content_id}.json",
                    headers=headers
                )
                
                if response.status_code == 200:
                    data = response.json()
                    field_data = data.get("data", {})
                    content = field_data.get("translation", "")
                    logger.info(f"Successfully retrieved locale field content")
                    
                    # Cache the content
                    cls._content_cache[content_id] = content
                    
                    # Log content preview
                    if len(content) > 100:
                        logger.info(f"Locale field {content_id} content preview: {content[:100]}...")
                    else:
                        logger.info(f"Locale field {content_id} content: {content}")
                    
                    return content
                else:
                    logger.error(f"Failed to get locale field content: {response.status_code} - {response.text}")
                    return ""
        except Exception as e:
            logger.error(f"Error getting locale field content: {str(e)}", exc_info=True)
            return ""
    
    @classmethod
    async def _process_article(cls, article: Dict[str, Any], query: str) -> Tuple[float, Dict[str, Any]]:
        """
        Process a single article to extract its content and calculate similarity score.
        
        Args:
            article: The article data
            query: The search query
            
        Returns:
            Tuple of (similarity_score, article)
        """
        # Extract article title and content
        title = ""
        content = ""
        content_id = None
        
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
        
        # Get content ID from contents array
        contents = article.get("contents", [])
        for content_obj in contents:
            if isinstance(content_obj, dict):
                # Check if it's a reference to a locale field
                if content_obj.get("resource_type") == "locale_field" and "id" in content_obj:
                    content_id = content_obj.get("id")
                    break
        
        # If we found a content ID, fetch the full content
        if content_id:
            content = await cls.get_locale_field_content(content_id)
        
        # Get keywords
        keywords = article.get("keywords", "")
        
        # If query is empty, just return the article without scoring
        if not query:
            return (0, article)
        
        # Calculate simple similarity score
        query_words = set(query.lower().split())
        title_words = set(title.lower().split())
        content_words = set(content.lower().split()) if content else set()
        keyword_words = set(keywords.lower().split()) if keywords else set()
        
        # Calculate overlap between query and article text
        title_overlap = len(query_words.intersection(title_words))
        content_overlap = len(query_words.intersection(content_words))
        keyword_overlap = len(query_words.intersection(keyword_words))
        
        # Weight the scores (content matches are now more important)
        similarity_score = (title_overlap * 2) + (content_overlap * 3) + (keyword_overlap * 2)
        
        return (similarity_score, article)
    
    @classmethod
    async def search_knowledge_base(cls, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Search the Kayako knowledge base for articles matching the query.
        Uses parallel processing for improved performance.
        
        Args:
            query: Search query
            limit: Maximum number of results to return
            
        Returns:
            List of matching articles
        """
        # Ensure we have a session ID
        session_id = await cls.authenticate()
        
        settings = get_settings()
        kayako_url = settings.KAYAKO_URL
        
        headers = {
            "X-Session-ID": session_id
        }
        
        logger.info(f"API request: Retrieving articles for query: '{query}'")
        try:
            # Fetch all articles with pagination
            all_articles = []
            next_url = f"{kayako_url}/api/v1/articles.json"
            page = 1
            
            async with httpx.AsyncClient() as client:
                while next_url and page <= 10:  # Limit to 10 pages to avoid infinite loops
                    logger.info(f"API request: Fetching page {page} of articles")
                    
                    # Extract the relative URL if it's a full URL
                    if next_url.startswith(kayako_url):
                        next_url = next_url[len(kayako_url):]
                    
                    # Make the request
                    response = await client.get(
                        f"{kayako_url}{next_url}",
                        headers=headers,
                        params={"include": "contents"} if "?" not in next_url else None
                    )
                    
                    if response.status_code == 200:
                        data = response.json()
                        page_articles = data.get("data", [])
                        all_articles.extend(page_articles)
                        logger.info(f"API response: Retrieved {len(page_articles)} articles from page {page}")
                        
                        # Check if there's a next page
                        next_url = data.get("next_url")
                        if not next_url:
                            break
                        
                        page += 1
                    else:
                        logger.error(f"API response: Failed to retrieve articles with status {response.status_code}: {response.text}")
                        break
                
                logger.info(f"API response: Retrieved a total of {len(all_articles)} articles from KB")
                
                if not all_articles:
                    logger.error("No articles found in the knowledge base")
                    return []
                
                # Process articles in parallel
                tasks = [cls._process_article(article, query) for article in all_articles]
                scored_articles = await asyncio.gather(*tasks)
                
                # Sort by similarity score (descending)
                scored_articles.sort(reverse=True, key=lambda x: x[0])
                
                # Return the top articles or all if limit is higher
                result_limit = min(limit, len(scored_articles)) if limit > 0 else len(scored_articles)
                top_articles = [article for score, article in scored_articles[:result_limit]]
                logger.info(f"API response: Found {len(top_articles)} relevant articles based on similarity")
                return top_articles
        except Exception as e:
            logger.error(f"API error: KB article retrieval failed: {str(e)}")
            return []
    
    @classmethod
    async def get_article_content(cls, article_id: int) -> Dict[str, Any]:
        """
        Get the content of a specific article by ID.
        
        Args:
            article_id: ID of the article to retrieve
            
        Returns:
            Article content
        """
        # Ensure we have a session ID
        session_id = await cls.authenticate()
        
        settings = get_settings()
        kayako_url = settings.KAYAKO_URL
        
        headers = {
            "X-Session-ID": session_id
        }
        
        logger.info(f"Getting article content for ID: {article_id}")
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{kayako_url}/api/v1/articles/{article_id}.json",
                    headers=headers,
                    params={"include": "contents"}
                )
                
                if response.status_code == 200:
                    data = response.json()
                    article = data.get("data", {})
                    logger.info(f"Successfully retrieved article content")
                    return article
                else:
                    logger.error(f"Failed to get article content: {response.status_code} - {response.text}")
                    return {}
        except Exception as e:
            logger.error(f"Error getting article content: {str(e)}", exc_info=True)
            return {}
    
    @classmethod
    async def create_ticket(cls, email: str, subject: str, content: str, tags: List[str] = None) -> Optional[Dict[str, Any]]:
        """
        Create a new ticket in Kayako.
        
        Args:
            email: Customer email
            subject: Ticket subject
            content: Ticket content/description
            tags: List of tags to apply to the ticket
            
        Returns:
            Created ticket data or None if creation failed
        """
        # Ensure we have a session ID
        session_id = await cls.authenticate()
        
        settings = get_settings()
        kayako_url = settings.KAYAKO_URL
        
        headers = {
            "X-Session-ID": session_id,
            "Content-Type": "application/json"
        }
        
        # Prepare ticket data
        ticket_data = {
            "subject": subject,
            "requester": {
                "email": email
            },
            "channel": "phone",
            "status": "new",
            "priority": "normal",
            "description": content
        }
        
        # Add tags if provided
        if tags:
            ticket_data["tags"] = tags
        
        logger.info(f"API request: Creating ticket for '{email}' with subject '{subject}'")
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{kayako_url}/api/v1/cases.json", 
                    headers=headers,
                    json=ticket_data
                )
                
                if response.status_code in (200, 201):
                    data = response.json()
                    ticket_id = data.get("id")
                    logger.info(f"API response: Ticket created successfully with ID: {ticket_id}")
                    return data
                else:
                    logger.error(f"API response: Ticket creation failed with status {response.status_code}")
                    return None
        except Exception as e:
            logger.error(f"API error: Ticket creation request failed: {str(e)}")
            return None
    
    @classmethod
    async def prepare_article_for_tts(cls, article: Dict[str, Any]) -> str:
        """
        Prepare article content for text-to-speech reading.
        
        Args:
            article: The article data
            
        Returns:
            Formatted article text ready for TTS
        """
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
        
        # Get content ID from contents array
        content = ""
        content_id = None
        contents = article.get("contents", [])
        for content_obj in contents:
            if isinstance(content_obj, dict):
                # Check if it's a reference to a locale field
                if content_obj.get("resource_type") == "locale_field" and "id" in content_obj:
                    content_id = content_obj.get("id")
                    break
        
        # If we found a content ID, fetch the full content
        if content_id:
            content = await cls.get_locale_field_content(content_id)
        
        # Clean up the content for TTS
        if content:
            # Remove HTML tags
            content = re.sub(r'<[^>]+>', ' ', content)
            # Replace multiple spaces with a single space
            content = re.sub(r'\s+', ' ', content)
            # Replace special characters
            content = content.replace('&nbsp;', ' ')
            content = content.replace('&amp;', 'and')
            content = content.replace('&lt;', 'less than')
            content = content.replace('&gt;', 'greater than')
            # Add periods after bullet points for better TTS pausing
            content = re.sub(r'•\s*', '. ', content)
        
        # Format the text for TTS
        tts_text = f"Article: {title}.\n\n{content}"
        
        logger.info(f"Prepared article '{title}' for TTS reading")
        return tts_text
    
    @classmethod
    async def get_top_article_for_tts(cls, query: str) -> Optional[str]:
        """
        Get the top matching article formatted for TTS reading.
        
        Args:
            query: Search query
            
        Returns:
            Formatted article text ready for TTS or None if no articles found
        """
        # Search for articles
        articles = await cls.search_knowledge_base(query, limit=1)
        
        if not articles:
            logger.info(f"No articles found for query: '{query}'")
            return None
        
        # Get the top article
        top_article = articles[0]
        
        # Prepare the article for TTS
        tts_text = await cls.prepare_article_for_tts(top_article)
        
        return tts_text 