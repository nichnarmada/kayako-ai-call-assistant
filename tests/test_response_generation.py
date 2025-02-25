import asyncio
import os
import sys
from dotenv import load_dotenv

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import services
from app.services.openai_service import OpenAIService
from app.services.kayako_service import KayakoService
from app.models.call import Conversation, CallState

# Load environment variables
load_dotenv()

async def test_response_generation():
    """Test the OpenAI response generation with article content."""
    print("Testing OpenAI response generation with article content...")
    
    # Test query
    query = "How do I change the name of my AdvocateHub?"
    print(f"\nQuery: '{query}'")
    
    # Initialize conversation
    call_sid = "test_call_123"
    conversation = Conversation(call_sid=call_sid)
    conversation.state = CallState.COLLECTING_ISSUE
    conversation.transcript.append(("AI", "How can I assist you today?"))
    conversation.transcript.append(("Customer", query))
    
    # Extract keywords
    print("\nExtracting keywords...")
    keyword_result = await OpenAIService.extract_search_keywords(query)
    keywords = keyword_result.get("keywords", "")
    print(f"Extracted keywords: '{keywords}'")
    
    # Search knowledge base
    print("\nSearching knowledge base...")
    articles = await KayakoService.search_knowledge_base(keywords, limit=3)
    print(f"Found {len(articles)} articles")
    
    if articles:
        # Get the top article
        top_article = articles[0]
        article_id = top_article.get("id", "unknown")
        
        # Extract title for display
        title = ""
        titles = top_article.get("titles", [])
        for title_obj in titles:
            if isinstance(title_obj, dict) and "translation" in title_obj:
                title = title_obj.get("translation", "")
                break
        
        if not title and "slugs" in top_article and top_article["slugs"]:
            for slug in top_article["slugs"]:
                if isinstance(slug, dict) and "translation" in slug:
                    slug_text = slug["translation"]
                    if "-" in slug_text:
                        slug_text = "-".join(slug_text.split("-")[1:])
                    title = " ".join(word.capitalize() for word in slug_text.split("-"))
                    break
        
        print(f"\nTop article: [ID: {article_id}] {title}")
        
        # Prepare article for TTS
        print("\nPreparing article for TTS...")
        tts_content = await KayakoService.prepare_article_for_tts(top_article)
        
        # Print the first 200 characters of the TTS content
        print("\nArticle content prepared for TTS (first 200 chars):")
        print("-" * 80)
        print(f"{tts_content[:200]}...")
        print("-" * 80)
        
        # Get the full article content
        print("\nGetting full article content...")
        full_article = await KayakoService.get_article_content(article_id)
        
        # Add the TTS content to the article for testing
        full_article["content"] = tts_content
        
        # Generate response with OpenAI
        print("\nGenerating response with OpenAI...")
        response_data = await OpenAIService.generate_response(
            query=query,
            articles=[full_article],
            conversation_history=conversation.transcript
        )
        
        response_message = response_data["text"]
        answer_found = response_data["answer_found"]
        
        print(f"\nAnswer found: {answer_found}")
        print(f"\nResponse message:")
        print("-" * 80)
        print(response_message)
        print("-" * 80)
        
        # Verify the result
        if answer_found:
            print("\n✅ SUCCESS: The system correctly identified that an answer was found!")
        else:
            print("\n❌ FAILURE: The system still thinks no answer was found.")
    else:
        print("\nNo articles found, cannot test response generation.")

async def main():
    """Run the test."""
    await test_response_generation()

if __name__ == "__main__":
    asyncio.run(main()) 