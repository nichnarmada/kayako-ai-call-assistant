import base64
import httpx
from typing import Dict, List, Optional, Any
from app.core.config import get_settings
from app.core.logger import logger

class KayakoService:
    """Service for interacting with Kayako's API."""
    
    # Store the session ID for reuse
    _session_id: Optional[str] = None
    
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
    async def search_knowledge_base(cls, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Search the Kayako knowledge base for articles matching the query.
        
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
        
        # Use the correct endpoint for searching articles
        params = {
            "query": query,
            "limit": limit,
            "include": "contents"  # Include article contents in the response
        }
        
        logger.info(f"API request: Searching KB for '{query}'")
        try:
            async with httpx.AsyncClient() as client:
                # Try using the helpcenter/articles endpoint
                response = await client.get(
                    f"{kayako_url}/api/v1/helpcenter/articles.json", 
                    headers=headers,
                    params=params
                )
                
                if response.status_code == 200:
                    data = response.json()
                    articles = data.get("data", [])
                    logger.info(f"API response: Found {len(articles)} articles in KB")
                    return articles
                else:
                    logger.info(f"API response: KB search failed with status {response.status_code}, trying unified search")
                    
                    # If that fails, try the unified search endpoint
                    response = await client.get(
                        f"{kayako_url}/api/v1/search.json",
                        headers=headers,
                        params={"query": query, "limit": limit, "resource_types": "helpcenter_article"}
                    )
                    
                    if response.status_code == 200:
                        data = response.json()
                        items = data.get("data", {}).get("items", [])
                        articles = [item.get("resource", {}) for item in items if item.get("resource_type") == "helpcenter_article"]
                        logger.info(f"API response: Found {len(articles)} articles via unified search")
                        return articles
                    else:
                        logger.error(f"API response: Unified search failed with status {response.status_code}")
                        return []
        except Exception as e:
            logger.error(f"API error: KB search request failed: {str(e)}")
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
                    f"{kayako_url}/api/v1/helpcenter/articles/{article_id}.json",
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