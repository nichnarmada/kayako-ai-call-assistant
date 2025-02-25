import asyncio
import os
import sys
from dotenv import load_dotenv

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import services
from app.services.openai_service import OpenAIService
from app.services.kayako_service import KayakoService

# Load environment variables
load_dotenv()

async def test_tts_content():
    """Test preparing article content for TTS reading."""
    print("Testing article content preparation for TTS...")
    
    # Test queries
    test_queries = [
        "How do I change the name of my AdvocateHub?",
        "I need to customize the login page for my hub",
        "How can I make my hub not show up in Google search results?"
    ]
    
    for query in test_queries:
        print("\n" + "=" * 80)
        print(f"Query: '{query}'")
        
        # First, extract keywords using OpenAI
        print("\nExtracting keywords...")
        keyword_result = await OpenAIService.extract_search_keywords(query)
        keywords = keyword_result.get("keywords", "")
        print(f"Extracted keywords: '{keywords}'")
        
        # Get the top article for TTS
        print("\nGetting top article for TTS...")
        tts_text = await KayakoService.get_top_article_for_tts(keywords)
        
        if tts_text:
            print("\nArticle content prepared for TTS:")
            print("-" * 40)
            # Print the first 500 characters with an ellipsis if longer
            if len(tts_text) > 500:
                print(f"{tts_text[:500]}...\n[Content truncated, total length: {len(tts_text)} characters]")
            else:
                print(tts_text)
            print("-" * 40)
        else:
            print("\nNo relevant article found for TTS reading.")
        
        print("=" * 80)

async def main():
    """Run the test."""
    await test_tts_content()

if __name__ == "__main__":
    asyncio.run(main()) 