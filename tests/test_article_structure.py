import asyncio
import os
import sys
import json
from dotenv import load_dotenv

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import services
from app.services.kayako_service import KayakoService

# Load environment variables
load_dotenv()

async def examine_article_structure():
    """Examine the structure of articles from Kayako."""
    print("Retrieving articles from Kayako...")
    
    # Get articles
    articles = await KayakoService.search_knowledge_base("", limit=5)  # Get a few articles
    
    if not articles:
        print("No articles found.")
        return
    
    print(f"\nFound {len(articles)} articles.")
    
    # Examine the first article in detail
    first_article = articles[0]
    print("\nExamining the structure of the first article:")
    print("=" * 80)
    
    # Print the article keys
    print(f"Article keys: {list(first_article.keys())}")
    
    # Check for title-related fields
    print("\nTitle-related fields:")
    if "title" in first_article:
        print(f"title: {first_article['title']}")
    
    if "titles" in first_article:
        print("\ntitles field structure:")
        titles = first_article["titles"]
        print(f"Type: {type(titles)}")
        print(f"Value: {json.dumps(titles, indent=2)}")
    
    # Check for content-related fields
    print("\nContent-related fields:")
    if "content" in first_article:
        print(f"content: {first_article['content'][:100]}...")
    
    if "contents" in first_article:
        print("\ncontents field structure:")
        contents = first_article["contents"]
        print(f"Type: {type(contents)}")
        print(f"Value: {json.dumps(contents, indent=2)}")
    
    # Print the full article structure (limited to avoid overwhelming output)
    print("\nFull article structure (first 1000 characters):")
    print(json.dumps(first_article, indent=2)[:1000])
    
    print("=" * 80)

async def main():
    """Run the test."""
    await examine_article_structure()

if __name__ == "__main__":
    asyncio.run(main()) 