import os
import time
import json
from datetime import datetime
import requests
from bs4 import BeautifulSoup
from openai import OpenAI
from urllib.parse import urljoin
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class WebScraper:
    def __init__(self):
        self.client = OpenAI(
            api_key=os.getenv('OPENAI_API_KEY')
        )
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        self.scrape_start_time = datetime.now()
        self.total_urls = 0
        self.processed_urls = 0

    def analyze_content(self, url, content):
        try:
            print("Analyzing content with OpenAI Assistant...")
            
            # Prepare the message with just the content, letting the assistant use its native instructions
            message_content = f"""
            URL: {url}
            
            Page Content:
            {content[:2000]}
            """
            
            # Create a thread
            thread = self.client.beta.threads.create()
            
            # Add a message to the thread
            message = self.client.beta.threads.messages.create(
                thread_id=thread.id,
                role="user",
                content=message_content
            )
            
            # Run the assistant
            run = self.client.beta.threads.runs.create(
                thread_id=thread.id,
                assistant_id=os.getenv('OPENAI_ASSISTANT_ID')
            )
            
            # Wait for the run to complete
            while True:
                run_status = self.client.beta.threads.runs.retrieve(
                    thread_id=thread.id,
                    run_id=run.id
                )
                if run_status.status == 'completed':
                    break
                elif run_status.status in ['failed', 'cancelled', 'expired']:
                    raise Exception(f"Assistant run failed with status: {run_status.status}")
                time.sleep(1)
            
            # Get the assistant's response
            messages = self.client.beta.threads.messages.list(
                thread_id=thread.id
            )
            
            # Get the latest assistant response
            for msg in messages:
                if msg.role == "assistant":
                    response_text = msg.content[0].text.value
                    
                    # Store the raw response as is, preserving the assistant's native format
                    analysis = {
                        "raw_analysis": response_text,
                        # You can add more structured fields here if needed
                    }
                    
                    print("✓ Content analyzed successfully")
                    return analysis
            
            raise Exception("No assistant response found")
            
        except Exception as e:
            print(f"✗ Error analyzing content: {str(e)}")
            return {
                "raw_analysis": "Analysis failed: " + str(e)
            }

    def scrape_url(self, url):
        try:
            print(f"\nScraping: {url}")
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extract metadata
            metadata = {
                'title': soup.title.string if soup.title else None,
                'description': soup.find('meta', {'name': 'description'})['content'] if soup.find('meta', {'name': 'description'}) else '',
                'h1': soup.h1.text if soup.h1 else None
            }
            
            # Extract main content
            main_content = ' '.join([p.text for p in soup.find_all('p')])
            
            # Truncate content if too long
            max_length = 2000
            if len(main_content) > max_length:
                main_content = main_content[:max_length] + '...'
            
            # Analyze content with OpenAI
            analysis = self.analyze_content(url, main_content)
            
            # Create the page data structure
            page_data = {
                "url": url,
                "metadata": metadata,
                "content": {
                    "main_text": main_content,
                    "word_count": len(main_content.split())
                },
                "scrape_status": {
                    "success": True,
                    "timestamp": datetime.now().isoformat()
                },
                "analysis": analysis
            }
            
            print("✓ Content scraped successfully")
            return page_data
            
        except Exception as e:
            error_msg = str(e)
            print(f"✗ Error scraping URL: {error_msg}")
            return {
                "url": url,
                "metadata": {},
                "content": {},
                "scrape_status": {
                    "success": False,
                    "error": error_msg,
                    "timestamp": datetime.now().isoformat()
                },
                "analysis": {}
            }

def main():
    # Read URLs from file
    with open('urls.txt', 'r', encoding='utf-8') as f:
        urls = [line.strip() for line in f if line.strip()]
    
    scraper = WebScraper()
    scraper.total_urls = len(urls)
    
    output_file = 'scraped_data.json'
    
    # Load existing results or initialize new ones
    if os.path.exists(output_file):
        try:
            with open(output_file, 'r', encoding='utf-8') as f:
                results = json.load(f)
                # Update timestamp and total URLs
                results["scrape_timestamp"] = datetime.now().isoformat()
                results["total_urls_processed"] = len(urls)
        except json.JSONDecodeError:
            # If file is corrupted, start fresh
            results = {
                "scrape_timestamp": datetime.now().isoformat(),
                "total_urls_processed": len(urls),
                "pages": []
            }
    else:
        # Initialize new results
        results = {
            "scrape_timestamp": datetime.now().isoformat(),
            "total_urls_processed": len(urls),
            "pages": []
        }
    
    # Process each URL
    for i, url in enumerate(urls, 1):
        print(f"\nProcessing URL {i} of {len(urls)}")
        
        # Check if URL has already been processed
        if any(page["url"] == url for page in results["pages"]):
            print(f"URL already processed: {url}")
            continue
            
        page_data = scraper.scrape_url(url)
        results["pages"].append(page_data)
        
        # Update the file after each URL
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        
        if i < len(urls):  # Don't wait after the last URL
            print("Waiting 2 seconds before next URL...")
            time.sleep(2)
    
    print(f"\n✓ Scraping completed! Results saved to {output_file}")

if __name__ == "__main__":
    main() 