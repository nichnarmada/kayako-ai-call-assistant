import asyncio
import os
import sys
from dotenv import load_dotenv

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import services
from app.services.kayako_service import KayakoService
from app.services.openai_service import OpenAIService
from app.models.call import Conversation, CallState

# Load environment variables
load_dotenv()

async def simulate_call_flow():
    """Simulate a full call flow to test the integration of all components."""
    print("Simulating a full call flow...")
    
    # Step 1: Initialize conversation
    call_sid = "test_call_123"
    conversation = Conversation(call_sid=call_sid)
    print("\n1. Initialized conversation")
    
    # Step 2: Collect email
    email = "john.doe@example.com"
    conversation.email = email
    conversation.state = CallState.COLLECTING_ISSUE
    conversation.transcript.append(("AI", "Thank you for calling Kayako Support. Please say your email address."))
    conversation.transcript.append(("Customer", email))
    print(f"\n2. Collected email: {email}")
    
    # Step 3: Collect issue
    issue = "I'm having trouble resetting my password. The reset link doesn't work."
    conversation.transcript.append(("AI", "How can I assist you today?"))
    conversation.transcript.append(("Customer", issue))
    conversation.state = CallState.PROCESSING
    print(f"\n3. Collected issue: {issue}")
    
    # Step 4: Search Kayako KB
    print("\n4. Searching Kayako KB...")
    
    # Extract keywords from the issue
    print("Extracting keywords from the issue...")
    keyword_result = await OpenAIService.extract_search_keywords(issue)
    search_query = keyword_result.get("keywords", issue)
    print(f"Original issue: '{issue}'")
    print(f"Extracted search query: '{search_query}'")
    
    # Search Kayako KB with the extracted keywords
    articles = await KayakoService.search_knowledge_base(search_query, limit=3)
    
    if articles:
        print(f"   Found {len(articles)} articles")
        
        # Get full article content
        full_articles = []
        for article in articles:
            article_id = article.get("id")
            if article_id:
                try:
                    full_article = await KayakoService.get_article_content(article_id)
                    full_articles.append(full_article)
                    print(f"   Retrieved content for article ID: {article_id}")
                except Exception as e:
                    print(f"   Error getting article content: {str(e)}")
                    full_articles.append(article)  # Use the original article if we can't get the full content
            else:
                full_articles.append(article)  # Use the original article if there's no ID
        
        # Step 5: Generate response with OpenAI
        print("\n5. Generating response with OpenAI...")
        response_data = await OpenAIService.generate_response(
            query=issue,
            articles=full_articles,
            conversation_history=conversation.transcript
        )
        
        response_message = response_data["text"]
        answer_found = response_data["answer_found"]
        
        print(f"   Response: {response_message}")
        print(f"   Answer found: {answer_found}")
        
        # Update conversation state
        conversation.state = CallState.RESPONDING
        conversation.transcript.append(("AI", response_message))
        
        if not answer_found:
            # Step 6: Create ticket if no answer found
            print("\n6. Creating ticket...")
            ticket_data = await OpenAIService.create_ticket_summary(conversation.transcript)
            
            print(f"   Ticket subject: {ticket_data['subject']}")
            print(f"   Ticket content: {ticket_data['content'][:100]}...")
            
            # In a real scenario, we would create the ticket in Kayako here
            print("   Ticket would be created in Kayako")
    else:
        print("   No articles found")
        
        # Step 6: Create ticket if no articles found
        print("\n6. Creating ticket...")
        ticket_data = await OpenAIService.create_ticket_summary(conversation.transcript)
        
        print(f"   Ticket subject: {ticket_data['subject']}")
        print(f"   Ticket content: {ticket_data['content'][:100]}...")
        
        # In a real scenario, we would create the ticket in Kayako here
        print("   Ticket would be created in Kayako")
    
    # Step 7: End call
    print("\n7. Call completed")
    print(f"   Final conversation state: {conversation.state}")
    print(f"   Transcript length: {len(conversation.transcript)} exchanges")
    
    return True

async def main():
    """Run the full integration test."""
    try:
        success = await simulate_call_flow()
        
        if success:
            print("\nFull integration test completed successfully!")
        else:
            print("\nFull integration test failed.")
    except Exception as e:
        print(f"\nError during full integration test: {str(e)}")

if __name__ == "__main__":
    asyncio.run(main()) 