import asyncio
import os
import sys
import time
from dotenv import load_dotenv

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import services
from app.services.openai_service import OpenAIService
from app.services.kayako_service import KayakoService

# Load environment variables
load_dotenv()

async def test_content_search():
    """Test searching articles with content-based similarity scoring."""
    print("Testing content-based search with parallel processing...")
    
    # Test queries
    test_queries = [
        "How do I change the name of my AdvocateHub?",
        "I need to customize the login page for my hub",
        "How can I make my hub not show up in Google search results?",
        "I want to add a new administrator to my hub",
        "How do I switch an admin account to a regular user account?"
    ]
    
    total_time = 0
    
    for query in test_queries:
        print("\n" + "=" * 80)
        print(f"Query: '{query}'")
        
        # First, extract keywords using OpenAI
        print("\nExtracting keywords...")
        start_time = time.time()
        keyword_result = await OpenAIService.extract_search_keywords(query)
        keywords = keyword_result.get("keywords", "")
        print(f"Extracted keywords: '{keywords}'")
        
        # Search with original query
        print("\nSearching with original query...")
        search_start_time = time.time()
        original_results = await KayakoService.search_knowledge_base(query, limit=3)
        search_time = time.time() - search_start_time
        total_time += search_time
        
        print(f"Found {len(original_results)} articles with original query in {search_time:.2f} seconds")
        
        if original_results:
            print("\nTop articles found with original query:")
            for i, article in enumerate(original_results):
                # Extract title
                title = ""
                article_id = article.get("id", "unknown")
                
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
                
                # If we couldn't find a title, check for slugs
                if not title and "slugs" in article and article["slugs"]:
                    for slug in article["slugs"]:
                        if isinstance(slug, dict) and "translation" in slug:
                            slug_text = slug["translation"]
                            # Remove the ID prefix if present
                            if "-" in slug_text:
                                clean_slug = "-".join(slug_text.split("-")[1:])
                            else:
                                clean_slug = slug_text
                            # Replace hyphens with spaces and capitalize words
                            title = " ".join(word.capitalize() for word in clean_slug.split("-"))
                            break
                
                # If we still don't have a title, use a placeholder
                if not title:
                    title = f"Untitled Article"
                
                print(f"  {i+1}. [ID: {article_id}] {title}")
        
        # Search with extracted keywords
        print("\nSearching with extracted keywords...")
        keyword_search_start_time = time.time()
        keyword_results = await KayakoService.search_knowledge_base(keywords, limit=3)
        keyword_search_time = time.time() - keyword_search_start_time
        total_time += keyword_search_time
        
        print(f"Found {len(keyword_results)} articles with extracted keywords in {keyword_search_time:.2f} seconds")
        
        if keyword_results:
            print("\nTop articles found with extracted keywords:")
            for i, article in enumerate(keyword_results):
                # Extract title
                title = ""
                article_id = article.get("id", "unknown")
                
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
                
                # If we couldn't find a title, check for slugs
                if not title and "slugs" in article and article["slugs"]:
                    for slug in article["slugs"]:
                        if isinstance(slug, dict) and "translation" in slug:
                            slug_text = slug["translation"]
                            # Remove the ID prefix if present
                            if "-" in slug_text:
                                clean_slug = "-".join(slug_text.split("-")[1:])
                            else:
                                clean_slug = slug_text
                            # Replace hyphens with spaces and capitalize words
                            title = " ".join(word.capitalize() for word in clean_slug.split("-"))
                            break
                
                # If we still don't have a title, use a placeholder
                if not title:
                    title = f"Untitled Article"
                
                print(f"  {i+1}. [ID: {article_id}] {title}")
        
        print("=" * 80)
    
    print(f"\nTotal search time for all queries: {total_time:.2f} seconds")
    print(f"Average search time per query: {total_time / (len(test_queries) * 2):.2f} seconds")
    
    # Check if content caching is working
    cache_size = len(KayakoService._content_cache)
    print(f"\nContent cache size: {cache_size} items")
    print(f"Cache hit rate will improve with subsequent searches")

async def main():
    """Run the test."""
    await test_content_search()

if __name__ == "__main__":
    asyncio.run(main()) 