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

async def test_keyword_extraction():
    """Test the keyword extraction functionality."""
    print("Testing keyword extraction...")
    
    # Test cases - various customer queries
    test_cases = [
        "Hi, I'm having trouble logging into my account. It keeps saying invalid password even though I'm sure it's correct.",
        "I purchased your product yesterday but haven't received any confirmation email yet.",
        "The app keeps crashing whenever I try to upload a file. It's really frustrating.",
        "I need help setting up the integration with Salesforce. The documentation is confusing.",
        "Can you tell me how to export my data? I need to move to a different system."
    ]
    
    for i, query in enumerate(test_cases):
        print(f"\nTest Case {i+1}: '{query}'")
        
        # Extract keywords
        print("Extracting keywords...")
        keyword_result = await OpenAIService.extract_search_keywords(query)
        keywords = keyword_result.get("keywords", "")
        
        print(f"Original query: '{query}'")
        print(f"Extracted keywords: '{keywords}'")
        
        # Search with original query
        print("\nSearching with original query...")
        original_articles = await KayakoService.search_knowledge_base(query, limit=3)
        print(f"Found {len(original_articles)} articles with original query")
        
        # Search with extracted keywords
        print("Searching with extracted keywords...")
        keyword_articles = await KayakoService.search_knowledge_base(keywords, limit=3)
        print(f"Found {len(keyword_articles)} articles with extracted keywords")
        
        # Compare results
        original_ids = [article.get("id") for article in original_articles]
        keyword_ids = [article.get("id") for article in keyword_articles]
        
        # Find unique articles in each search
        unique_to_original = set(original_ids) - set(keyword_ids)
        unique_to_keywords = set(keyword_ids) - set(original_ids)
        common = set(original_ids).intersection(set(keyword_ids))
        
        print(f"Articles found only with original query: {len(unique_to_original)}")
        print(f"Articles found only with keywords: {len(unique_to_keywords)}")
        print(f"Articles found in both searches: {len(common)}")
        
        print("-" * 50)

async def main():
    """Run the test."""
    await test_keyword_extraction()

if __name__ == "__main__":
    asyncio.run(main()) 