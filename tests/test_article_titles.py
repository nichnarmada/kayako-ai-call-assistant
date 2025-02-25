import asyncio
import os
import sys
from dotenv import load_dotenv

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import services
from app.services.kayako_service import KayakoService

# Load environment variables
load_dotenv()

async def get_article_titles():
    """Retrieve articles from Kayako and print their titles."""
    print("Retrieving all articles from Kayako (with pagination)...")
    
    # Get all articles (passing 0 or a negative number will return all articles)
    articles = await KayakoService.search_knowledge_base("", limit=0)
    
    print(f"\nFound {len(articles)} articles:")
    print("=" * 80)
    
    # Extract and print titles
    for i, article in enumerate(articles):
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
        
        # If we couldn't find a title in the titles array, try the title field directly
        if not title and "title" in article:
            title = article["title"]
            
        # If we still don't have a title, check for slugs
        slug_text = ""
        if "slugs" in article and article["slugs"]:
            for slug in article["slugs"]:
                if isinstance(slug, dict) and "translation" in slug:
                    slug_text = slug["translation"]
                    break
                    
        if not title and slug_text:
            # Extract a readable title from the slug
            # Remove the ID prefix if present (e.g., "54-changing-the-name..." -> "changing-the-name...")
            if "-" in slug_text:
                clean_slug = "-".join(slug_text.split("-")[1:])
            else:
                clean_slug = slug_text
            # Replace hyphens with spaces and capitalize words
            title = " ".join(word.capitalize() for word in clean_slug.split("-"))
            
        # If we still don't have a title, use a placeholder
        if not title:
            title = f"Untitled Article"
            
        print(f"{i+1}. [ID: {article_id}] {title}")
        if slug_text:
            print(f"   Slug: {slug_text}")
        print()
    
    print("=" * 80)

async def main():
    """Run the test."""
    await get_article_titles()

if __name__ == "__main__":
    asyncio.run(main()) 