import asyncio
import os
import sys
from dotenv import load_dotenv

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import the OpenAI service
from app.services.openai_service import OpenAIService
from app.services.kayako_service import KayakoService

# Load environment variables
load_dotenv()

async def test_generate_response():
    """Test OpenAI response generation."""
    print("Testing OpenAI response generation...")
    
    # Test query
    query = "How do I reset my password?"
    
    try:
        # First, search Kayako KB for articles
        print(f"Searching Kayako KB for: {query}")
        articles = await KayakoService.search_knowledge_base(query, limit=3)
        
        if not articles:
            print("No articles found in Kayako KB")
            return False
        
        print(f"Found {len(articles)} articles")
        
        # Get full article content
        full_articles = []
        for article in articles:
            article_id = article.get("id")
            if article_id:
                try:
                    full_article = await KayakoService.get_article_content(article_id)
                    full_articles.append(full_article)
                except Exception as e:
                    print(f"Error getting article content: {str(e)}")
                    full_articles.append(article)  # Use the original article if we can't get the full content
            else:
                full_articles.append(article)  # Use the original article if there's no ID
        
        # Generate response with OpenAI
        print("Generating response with OpenAI...")
        conversation_history = [
            ("AI", "Thank you for calling Kayako Support. Please say your email address."),
            ("Customer", "john.doe@example.com"),
            ("AI", "How can I assist you today?"),
            ("Customer", query)
        ]
        
        response_data = await OpenAIService.generate_response(
            query=query,
            articles=full_articles,
            conversation_history=conversation_history
        )
        
        print("\nGenerated Response:")
        print(f"Text: {response_data['text']}")
        print(f"Answer found: {response_data['answer_found']}")
        if "usage" in response_data:
            print(f"Token usage: {response_data['usage']}")
        
        return True
    except Exception as e:
        print(f"Error generating response: {str(e)}")
        return False

async def test_create_ticket_summary():
    """Test OpenAI ticket summary generation."""
    print("\nTesting OpenAI ticket summary generation...")
    
    try:
        # Sample conversation history
        conversation_history = [
            ("AI", "Thank you for calling Kayako Support. Please say your email address."),
            ("Customer", "john.doe@example.com"),
            ("AI", "How can I assist you today?"),
            ("Customer", "I'm having trouble with the API integration. The documentation says to use the v2 endpoint, but it's not working."),
            ("AI", "I don't have enough information about that in my knowledge base. I'll create a ticket for you and have an agent follow up.")
        ]
        
        # Generate ticket summary
        print("Generating ticket summary...")
        ticket_data = await OpenAIService.create_ticket_summary(conversation_history)
        
        print("\nGenerated Ticket Summary:")
        print(f"Subject: {ticket_data['subject']}")
        print(f"Content: {ticket_data['content']}")
        
        return True
    except Exception as e:
        print(f"Error generating ticket summary: {str(e)}")
        return False

async def main():
    """Run all tests."""
    # Test OpenAI response generation
    response_success = await test_generate_response()
    
    # Test ticket summary generation
    summary_success = await test_create_ticket_summary()
    
    if response_success and summary_success:
        print("\nAll tests passed!")
    else:
        print("\nSome tests failed.")

if __name__ == "__main__":
    asyncio.run(main()) 