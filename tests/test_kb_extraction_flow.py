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

# Sample knowledge base articles (titles) that exist in Kayako
SAMPLE_KB_ARTICLES = [
    "Changing the Name of Your AdvocateHub",
    "Customizing your Hub's sign in page",
    "Customizing AdvocateHub Branding",
    "Advanced Branding: Custom Headers, Fonts, and CSS Stylesheets",
    "Customizing the CSS of an AdvocateHub Web Element",
    "Removing Social Login Buttons from Elevated Login Page",
    "How to Make Your AdvocateHub Platform Unsearchable by Search Engines",
    "Adding Administrators to AdvocateHub",
    "Upgrading Advocate accounts to Administrator accounts",
    "How to Edit an Administrator Profile",
    "Switching an Administrator Account to an Advocate Account",
    "Contact Admin Form",
    "Administrator Role Permissions Management",
    "Single Sign-On (SSO) Issues for Admin Users",
    "Resolving Contact Sync Issues in Stream Portal"
]

# Test cases - customer queries related to the sample KB articles
TEST_CASES = [
    "I need to change the name of my hub, how do I do that?",
    "How can I customize the login page for my hub?",
    "I want to change the branding of my AdvocateHub",
    "Can you help me with custom CSS for my hub?",
    "I need to remove the social login buttons from my login page",
    "How do I make my hub not show up in Google search?",
    "I want to add a new admin to my hub",
    "How do I upgrade a regular user to an admin?",
    "I need to edit an admin's profile information",
    "I want to change an admin back to a regular user",
    "Where is the contact admin form?",
    "How do I manage admin permissions?",
    "My SSO isn't working for admin users",
    "I'm having issues with contact sync in Stream Portal"
]

async def simulate_customer_flow(query):
    """Simulate the customer flow from query to knowledge base article retrieval."""
    print(f"\nCustomer Query: '{query}'")
    
    # Step 1: Extract keywords from the customer query
    print("\nStep 1: Extracting keywords...")
    keyword_result = await OpenAIService.extract_search_keywords(query)
    keywords = keyword_result.get("keywords", "")
    print(f"Extracted keywords: '{keywords}'")
    
    # Step 2: Search Kayako KB with the original query
    print("\nStep 2: Searching with original query...")
    original_articles = await KayakoService.search_knowledge_base(query, limit=5)
    print(f"Found {len(original_articles)} articles with original query")
    
    if original_articles:
        print("Top articles found with original query:")
        for i, article in enumerate(original_articles[:3]):
            print(f"  {i+1}. {article.get('title', 'Untitled')}")
    
    # Step 3: Search Kayako KB with the extracted keywords
    print("\nStep 3: Searching with extracted keywords...")
    keyword_articles = await KayakoService.search_knowledge_base(keywords, limit=5)
    print(f"Found {len(keyword_articles)} articles with extracted keywords")
    
    if keyword_articles:
        print("Top articles found with extracted keywords:")
        for i, article in enumerate(keyword_articles[:3]):
            print(f"  {i+1}. {article.get('title', 'Untitled')}")
    
    # Step 4: Analyze the results
    print("\nStep 4: Analyzing results...")
    
    # Check if the expected article is in the results
    expected_articles = [article for article in SAMPLE_KB_ARTICLES if any(word.lower() in article.lower() for word in query.lower().split())]
    
    original_titles = [article.get('title', '') for article in original_articles]
    keyword_titles = [article.get('title', '') for article in keyword_articles]
    
    found_in_original = any(expected in original_titles for expected in expected_articles)
    found_in_keywords = any(expected in keyword_titles for expected in expected_articles)
    
    print(f"Expected to find articles related to: {', '.join(expected_articles)}")
    print(f"Found expected article with original query: {'Yes' if found_in_original else 'No'}")
    print(f"Found expected article with extracted keywords: {'Yes' if found_in_keywords else 'No'}")
    
    # Step 5: Generate a response using OpenAI
    print("\nStep 5: Generating response with OpenAI...")
    response = await OpenAIService.generate_response(
        query=query,
        articles=keyword_articles if keyword_articles else original_articles,
        conversation_history=[("AI", "How can I help you today?"), ("Customer", query)]
    )
    
    print(f"AI Response: '{response.get('text', '')[:150]}...'")
    print(f"Answer found: {'Yes' if response.get('answer_found', False) else 'No'}")
    
    print("-" * 80)
    return {
        "query": query,
        "keywords": keywords,
        "original_articles": original_articles,
        "keyword_articles": keyword_articles,
        "expected_articles": expected_articles,
        "found_in_original": found_in_original,
        "found_in_keywords": found_in_keywords,
        "response": response
    }

async def run_tests():
    """Run tests for all the test cases."""
    print("Starting customer flow simulation with keyword extraction...")
    
    results = []
    for query in TEST_CASES:
        result = await simulate_customer_flow(query)
        results.append(result)
    
    # Print summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    
    success_original = sum(1 for r in results if r["found_in_original"])
    success_keywords = sum(1 for r in results if r["found_in_keywords"])
    
    print(f"Total test cases: {len(TEST_CASES)}")
    print(f"Success rate with original queries: {success_original}/{len(TEST_CASES)} ({success_original/len(TEST_CASES)*100:.1f}%)")
    print(f"Success rate with extracted keywords: {success_keywords}/{len(TEST_CASES)} ({success_keywords/len(TEST_CASES)*100:.1f}%)")
    
    improvement = success_keywords - success_original
    if improvement > 0:
        print(f"Keyword extraction improved results in {improvement} cases ({improvement/len(TEST_CASES)*100:.1f}%)")
    elif improvement < 0:
        print(f"Keyword extraction worsened results in {abs(improvement)} cases ({abs(improvement)/len(TEST_CASES)*100:.1f}%)")
    else:
        print("Keyword extraction had no overall impact on search results")

async def main():
    """Run the test."""
    await run_tests()

if __name__ == "__main__":
    asyncio.run(main()) 