import asyncio
import os
import sys
from dotenv import load_dotenv

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import the Kayako service
from app.services.kayako_service import KayakoService

# Load environment variables
load_dotenv()

async def test_authentication():
    """Test Kayako authentication."""
    print("Testing Kayako authentication...")
    
    try:
        session_id = await KayakoService.authenticate()
        print(f"Authentication successful! Session ID: {session_id[:10]}...")
        return True
    except Exception as e:
        print(f"Authentication failed: {str(e)}")
        return False

async def test_get_user_info():
    """Test getting user information."""
    print("\nTesting getting user information...")
    
    try:
        user_info = await KayakoService.get_user_info()
        print(f"Successfully retrieved user information:")
        print(f"Name: {user_info.get('full_name', 'N/A')}")
        print(f"Email: {user_info.get('email', 'N/A')}")
        print(f"Role: {user_info.get('role', 'N/A')}")
        return True
    except Exception as e:
        print(f"Failed to get user info: {str(e)}")
        return False

async def test_kb_search():
    """Test Kayako knowledge base search."""
    print("\nTesting Kayako KB search...")
    
    # Test query
    query = "password reset"
    
    try:
        articles = await KayakoService.search_knowledge_base(query)
        print(f"Found {len(articles)} articles matching '{query}'")
        
        # Print article titles
        for i, article in enumerate(articles, 1):
            print(f"{i}. {article.get('title', 'No title')}")
            
        return True
    except Exception as e:
        print(f"KB search failed: {str(e)}")
        return False

async def main():
    """Run all tests."""
    # Test authentication first
    auth_success = await test_authentication()
    
    if auth_success:
        # If authentication succeeds, test getting user info
        await test_get_user_info()
        
        # Test KB search
        await test_kb_search()
    else:
        print("Skipping user info and KB search tests due to authentication failure.")

if __name__ == "__main__":
    asyncio.run(main()) 