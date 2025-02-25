import asyncio
import os
import sys
import uuid
from dotenv import load_dotenv

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import services and models
from app.services.openai_service import OpenAIService
from app.services.kayako_service import KayakoService
from app.models.call import Conversation, CallState

# Load environment variables
load_dotenv()

async def simulate_full_flow():
    """Simulate the full flow of the application, including TTS content reading."""
    print("Simulating full call flow with TTS content reading...")
    
    # Generate a mock call SID
    call_sid = f"test_call_{uuid.uuid4().hex[:8]}"
    
    # Initialize conversation
    conversation = Conversation(call_sid=call_sid)
    conversation.state = CallState.COLLECTING_ISSUE
    
    # Test customer query
    customer_query = "How do I change the name of my AdvocateHub?"
    print(f"\nCustomer query: '{customer_query}'")
    
    # Add to transcript
    conversation.transcript.append(("AI", "How can I assist you today?"))
    conversation.transcript.append(("Customer", customer_query))
    
    # Extract keywords
    print("\nExtracting keywords...")
    keyword_result = await OpenAIService.extract_search_keywords(customer_query)
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
        
        # Print the TTS content (truncated if too long)
        print("\nArticle content prepared for TTS:")
        print("-" * 80)
        if len(tts_content) > 500:
            print(f"{tts_content[:500]}...\n[Content truncated, total length: {len(tts_content)} characters]")
        else:
            print(tts_content)
        print("-" * 80)
        
        # Generate response with OpenAI
        print("\nGenerating response with OpenAI...")
        response_data = await OpenAIService.generate_response(
            query=customer_query,
            articles=[top_article],
            conversation_history=conversation.transcript
        )
        
        response_message = response_data["text"]
        answer_found = response_data["answer_found"]
        
        print(f"\nAnswer found: {answer_found}")
        print(f"Response message: '{response_message}'")
        
        # Simulate TTS response
        print("\nSimulating TTS response...")
        if answer_found:
            intro_message = "I found an article that answers your question. Here it is: "
            full_message = f"{intro_message} {tts_content} Thank you for calling Kayako Support. Have a great day!"
            print("\nFull TTS message would be:")
            print("-" * 80)
            print(f"{intro_message}")
            print(f"[Article content would be read here, {len(tts_content)} characters]")
            print("Thank you for calling Kayako Support. Have a great day!")
            print("-" * 80)
        else:
            print("\nNo answer found, would collect email and create ticket.")
    else:
        print("\nNo articles found, would collect email and create ticket.")

async def main():
    """Run the test."""
    await simulate_full_flow()

if __name__ == "__main__":
    asyncio.run(main()) 