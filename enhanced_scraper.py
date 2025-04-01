import os
import time
import json
import re
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup
import extruct
from w3lib.html import get_base_url
from PIL import Image
from io import BytesIO
import logging
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv
import base64
from screenshot_manager import ScreenshotManager
import openai
from openai import OpenAI
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import random
from urllib.robotparser import RobotFileParser

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class ImageData:
    url: str
    alt: str
    title: Optional[str]
    width: Optional[int]
    height: Optional[int]
    file_size: Optional[int]
    format: Optional[str]
    is_data_url: bool = False

@dataclass
class LinkData:
    url: str
    anchor_text: str
    is_internal: bool
    is_nofollow: bool
    status_code: Optional[int]
    depth: Optional[int]

@dataclass
class HeadingData:
    level: int  # 1-6 for h1-h6
    text: str
    word_count: int

@dataclass
class StructuredData:
    schema_org: Dict
    open_graph: Dict
    twitter_cards: Dict
    microdata: Dict
    rdfa: Dict
    json_ld: List[Dict]

class EnhancedWebScraper:
    def __init__(self):
        # Initialize other components first
        self.screenshot_manager = ScreenshotManager()
        
        # List of realistic user agents
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 Edg/122.0.0.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3.1 Safari/605.1.15',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0'
        ]
        
        # Common browser headers
        self.browser_headers = {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9,he;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'DNT': '1',  # Do Not Track
            'Cache-Control': 'max-age=0'
        }
        
        # Initialize requests session with retry strategy and timeouts
        from requests.adapters import HTTPAdapter
        from urllib3.util.retry import Retry
        
        # Configure retry strategy with exponential backoff
        retry_strategy = Retry(
            total=3,  # number of retries
            backoff_factor=2,  # wait 2, 4, 8 seconds between retries
            status_forcelist=[429, 500, 502, 503, 504],  # HTTP status codes to retry on
            allowed_methods=["GET", "HEAD", "OPTIONS"]  # Only retry on these methods
        )
        
        # Create session with retry strategy
        self.session = requests.Session()
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        # Set default timeout (connect timeout, read timeout)
        self.session.timeout = (15, 45)  # 15 seconds to connect, 45 seconds to read
        
        # Initialize robots.txt parser
        self.robots_parser = RobotFileParser()
        
        # Track request history to implement rate limiting
        self.last_request_time = {}  # Dictionary to track last request time per domain
        self.min_request_interval = 5  # Minimum seconds between requests to the same domain
        
        # Initialize OpenAI client
        try:
            api_key = os.getenv('OPENAI_API_KEY')
            if not api_key:
                raise ValueError("OPENAI_API_KEY environment variable is not set")
            self.client = OpenAI(api_key=api_key)
            self.assistant_id = "asst_pMeB1BJP8A7kwVSJQKTY1kSd"
        except Exception as e:
            logger.error(f"Failed to initialize OpenAI client: {str(e)}")
            self.client = None
            self.assistant_id = None
            
    def get_random_user_agent(self):
        """Get a random user agent from the list."""
        return random.choice(self.user_agents)
        
    def get_request_headers(self, url):
        """Get headers for a request with proper referrer and origin."""
        parsed_url = urlparse(url)
        base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
        
        headers = self.browser_headers.copy()
        headers.update({
            'User-Agent': self.get_random_user_agent(),
            'Host': parsed_url.netloc,
            'Origin': base_url,
            'Referer': base_url
        })
        return headers
        
    def respect_robots_txt(self, url: str) -> bool:
        """Check if we're allowed to scrape the URL according to robots.txt."""
        try:
            parsed_url = urlparse(url)
            robots_url = f"{parsed_url.scheme}://{parsed_url.netloc}/robots.txt"
            
            # Use session with proper headers for robots.txt request
            headers = self.get_request_headers(robots_url)
            response = self.session.get(robots_url, headers=headers, timeout=(5, 10))
            
            if response.status_code == 200:
                self.robots_parser.parse(response.text.splitlines())
                return self.robots_parser.can_fetch("*", url)
            return True
        except Exception as e:
            logger.warning(f"Error checking robots.txt: {str(e)}")
            return True
            
    def respect_rate_limits(self, url: str):
        """Implement rate limiting per domain."""
        parsed_url = urlparse(url)
        domain = parsed_url.netloc
        
        current_time = time.time()
        if domain in self.last_request_time:
            time_since_last_request = current_time - self.last_request_time[domain]
            if time_since_last_request < self.min_request_interval:
                sleep_time = self.min_request_interval - time_since_last_request
                logger.info(f"Rate limiting: Sleeping for {sleep_time:.2f} seconds")
                time.sleep(sleep_time)
                
        # Add some random delay (2-7 seconds)
        random_delay = random.uniform(2, 7)
        time.sleep(random_delay)
        
        self.last_request_time[domain] = time.time()
        
    def get_image_data(self, img_tag: BeautifulSoup, base_url: str) -> ImageData:
        """Extract image data from img tag."""
        try:
            # Skip tracking pixels and non-image URLs
            src = img_tag.get('src', '')
            if any(x in src.lower() for x in ['facebook.com/tr', 'pixel', 'tracking', 'analytics']):
                return None
                
            # Skip data URLs that aren't images
            if src.startswith('data:'):
                if not src.startswith('data:image/'):
                    return None
                    
            # Skip empty or invalid URLs
            if not src or src.startswith('javascript:'):
                return None
                
            # Handle relative URLs
            if not src.startswith(('http://', 'https://', 'data:')):
                src = urljoin(base_url, src)
                
            # Get image dimensions
            width = img_tag.get('width')
            height = img_tag.get('height')
            
            # Get alt text and title
            alt = img_tag.get('alt', '')
            title = img_tag.get('title')
            
            # For data URLs, we already have the image data
            if src.startswith('data:'):
                return ImageData(
                    url=src,
                    alt=alt,
                    title=title,
                    width=width,
                    height=height,
                    is_data_url=True
                )
            
            # For regular URLs, fetch the image
            try:
                response = self.session.get(src, timeout=(5, 10))
                if response.status_code == 200:
                    img_data = BytesIO(response.content)
                    img = Image.open(img_data)
                    return ImageData(
                        url=src,
                        alt=alt,
                        title=title,
                        width=width or img.width,
                        height=height or img.height,
                        file_size=len(response.content),
                        format=img.format
                    )
            except Exception as e:
                logger.warning(f"Failed to process image {src}: {str(e)}")
                return None
                
        except Exception as e:
            logger.warning(f"Error processing image tag: {str(e)}")
            return None

    def get_link_data(self, link_tag: BeautifulSoup, base_url: str) -> LinkData:
        """Extract comprehensive link data including status and depth."""
        try:
            href = link_tag.get('href', '')
            if not href:
                return None

            # Skip javascript: and mailto: links
            if href.startswith(('javascript:', 'mailto:', 'tel:')):
                return None

            url = urljoin(base_url, href)
            is_internal = urlparse(url).netloc == urlparse(base_url).netloc
            
            # Check link status
            status_code = None
            if is_internal:
                try:
                    response = self.session.head(url, allow_redirects=True)
                    status_code = response.status_code
                except:
                    pass

            return LinkData(
                url=url,
                anchor_text=link_tag.get_text(strip=True),
                is_internal=is_internal,
                is_nofollow='nofollow' in link_tag.get('rel', ''),
                status_code=status_code,
                depth=None  # To be calculated later
            )
        except Exception as e:
            logger.warning(f"Failed to process link {href}: {str(e)}")
            return None

    def get_structured_data(self, html: str, url: str) -> StructuredData:
        """Extract all forms of structured data from the page."""
        try:
            base_url = get_base_url(html, url)
            structured_data = extruct.extract(
                html,
                base_url=base_url,
                syntaxes=['json-ld', 'microdata', 'opengraph', 'rdfa', 'microformat'],
                uniform=True
            )
            
            # Extract Twitter Card metadata
            soup = BeautifulSoup(html, 'html.parser')
            twitter_cards = {}
            twitter_meta = soup.find_all('meta', attrs={'name': re.compile('^twitter:')})
            for meta in twitter_meta:
                name = meta.get('name', '').lower()
                content = meta.get('content', '')
                twitter_cards[name] = content
            
            return StructuredData(
                schema_org=structured_data.get('json-ld', []),
                open_graph=structured_data.get('opengraph', []),
                twitter_cards=twitter_cards,
                microdata=structured_data.get('microdata', []),
                rdfa=structured_data.get('rdfa', []),
                json_ld=structured_data.get('json-ld', [])
            )
        except Exception as e:
            logger.warning(f"Failed to extract structured data: {str(e)}")
            return None

    def analyze_content(self, url: str, html_content: str, metadata: Dict) -> Dict:
        """Analyze content using OpenAI API with rate limiting."""
        if not self.client or not self.assistant_id:
            return {"error": "OpenAI client not initialized"}
            
        try:
            # Create a thread
            thread = self.client.beta.threads.create()
            
            # Add the content as a message
            self.client.beta.threads.messages.create(
                thread_id=thread.id,
                role="user",
                content=html_content
            )
            
            # Run the assistant
            run = self.client.beta.threads.runs.create(
                thread_id=thread.id,
                assistant_id=self.assistant_id
            )
            
            # Poll for completion with delay
            while True:
                run_status = self.client.beta.threads.runs.retrieve(
                    thread_id=thread.id,
                    run_id=run.id
                )
                
                if run_status.status == 'completed':
                    break
                elif run_status.status == 'failed':
                    return {"error": "Analysis failed"}
                    
                time.sleep(1)  # Add delay between polls
            
            # Get the response
            messages = self.client.beta.threads.messages.list(
                thread_id=thread.id
            )
            
            # Clean up
            self.client.beta.threads.delete(thread.id)
            
            return {"analysis": messages.data[0].content[0].text.value}
            
        except Exception as e:
            logger.error(f"Error in content analysis: {str(e)}")
            return {"error": str(e)}

    def scrape_url(self, url: str, take_screenshots: bool = True) -> Dict:
        """Enhanced scraping with comprehensive data extraction and safety measures."""
        try:
            # Check robots.txt first
            if not self.respect_robots_txt(url):
                return {
                    "url": url,
                    "status": {"success": False, "error": "Access denied by robots.txt"},
                    "error": "Access denied by robots.txt"
                }
                
            logger.info(f"Scraping: {url}")
            start_time = time.time()
            
            # Respect rate limits
            self.respect_rate_limits(url)
            
            # Get proper headers for this request
            headers = self.get_request_headers(url)
            
            # Take screenshots first (with error handling)
            screenshots = {}
            if take_screenshots:
                try:
                    logger.info("Taking screenshots...")
                    screenshots = self.screenshot_manager.take_screenshots(url)
                except Exception as e:
                    logger.warning(f"Failed to take screenshots: {str(e)}")
                    screenshots = {
                        "error": str(e),
                        "status": "failed"
                    }
            else:
                screenshots = {
                    "status": "disabled",
                    "message": "Screenshots were disabled for this scrape"
                }
            
            # Fetch page with updated headers
            try:
                response = self.session.get(url, headers=headers, timeout=self.session.timeout)
                response.raise_for_status()
            except requests.exceptions.Timeout:
                logger.error(f"✗ Timeout while scraping {url}")
                return {
                    "url": url,
                    "status": {"success": False, "error": "Request timed out"},
                    "error": "Request timed out"
                }
            except requests.exceptions.ConnectionError as e:
                logger.error(f"✗ Connection error while scraping {url}: {str(e)}")
                return {
                    "url": url,
                    "status": {"success": False, "error": "Connection error"},
                    "error": str(e)
                }
            except requests.exceptions.RequestException as e:
                logger.error(f"✗ Error scraping {url}: {str(e)}")
                return {
                    "url": url,
                    "status": {"success": False, "error": "Request failed"},
                    "error": str(e)
                }
            
            # Parse HTML
            soup = BeautifulSoup(response.text, 'html.parser')
            self.base_url = url

            # Basic metadata
            metadata = {
                'title': soup.title.string.strip() if soup.title else None,
                'description': soup.find('meta', {'name': 'description'})['content'] if soup.find('meta', {'name': 'description'}) else None,
                'robots': soup.find('meta', {'name': 'robots'})['content'] if soup.find('meta', {'name': 'robots'}) else None,
                'keywords': soup.find('meta', {'name': 'keywords'})['content'] if soup.find('meta', {'name': 'keywords'}) else None,
                'author': soup.find('meta', {'name': 'author'})['content'] if soup.find('meta', {'name': 'author'}) else None,
                'language': soup.find('html').get('lang') if soup.find('html') else None,
                'canonical': soup.find('link', {'rel': 'canonical'})['href'] if soup.find('link', {'rel': 'canonical'}) else None,
                'hreflang': [{'href': tag['href'], 'lang': tag['hreflang']} for tag in soup.find_all('link', {'rel': 'alternate', 'hreflang': True})],
                'viewport': soup.find('meta', {'name': 'viewport'})['content'] if soup.find('meta', {'name': 'viewport'}) else None,
            }

            # Extract headings
            headings = []
            for level in range(1, 7):
                for heading in soup.find_all(f'h{level}'):
                    text = heading.get_text(strip=True)
                    headings.append(HeadingData(
                        level=level,
                        text=text,
                        word_count=len(text.split())
                    ))

            # Extract images
            images = []
            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = [
                    executor.submit(self.get_image_data, img, url)
                    for img in soup.find_all('img')
                ]
                images = [f.result() for f in futures if f.result()]

            # Extract links
            links = []
            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = [
                    executor.submit(self.get_link_data, link, url)
                    for link in soup.find_all('a')
                ]
                links = [f.result() for f in futures if f.result()]

            # Extract structured data
            structured_data = self.get_structured_data(response.text, url)

            # Technical data
            technical = {
                'load_time': time.time() - start_time,
                'page_size': len(response.content),
                'status_code': response.status_code,
                'content_type': response.headers.get('content-type'),
                'scripts': [script['src'] for script in soup.find_all('script', src=True)],
                'stylesheets': [css['href'] for css in soup.find_all('link', rel='stylesheet')],
            }

            # Create the enhanced page data structure
            page_data = {
                "url": url,
                "scrape_timestamp": datetime.now().isoformat(),
                "metadata": metadata,
                "content": {
                    "full_html": response.text,
                    "clean_text": ' '.join([p.get_text(strip=True) for p in soup.find_all('p')]),
                    "word_count": len(response.text.split()),
                },
                "headings": [asdict(h) for h in headings],
                "images": [asdict(img) for img in images],
                "links": [asdict(link) for link in links],
                "structured_data": asdict(structured_data) if structured_data else {},
                "technical": technical,
                "status": {
                    "success": True,
                    "message": "Successfully scraped"
                },
                "screenshots": screenshots,
                "analysis": {
                    "raw_analysis": "Content analysis not available. OpenAI client not initialized."
                }
            }

            # Analyze content using OpenAI if client is available
            if self.client:
                content_analysis = self.analyze_content(url, response.text, metadata)
                page_data["analysis"] = content_analysis

            logger.info(f"✓ Successfully scraped {url}")
            return page_data

        except Exception as e:
            error_msg = str(e)
            logger.error(f"✗ Error scraping {url}: {error_msg}")
            return {
                "url": url,
                "scrape_timestamp": datetime.now().isoformat(),
                "status": {
                    "success": False,
                    "message": error_msg
                },
                "screenshots": {
                    "status": "failed",
                    "message": "Screenshots not available due to scraping error"
                },
                "analysis": {
                    "raw_analysis": f"Analysis failed: {error_msg}"
                }
            }

def main():
    # Initialize scraper
    scraper = EnhancedWebScraper()
    
    # Read URLs from file
    with open('urls.txt', 'r', encoding='utf-8') as f:
        urls = [line.strip() for line in f if line.strip()]
    
    # Initialize results
    results = {
        "scrape_timestamp": datetime.now().isoformat(),
        "total_urls": len(urls),
        "pages": []
    }
    
    # Process each URL
    for url in urls:
        page_data = scraper.scrape_url(url)
        results["pages"].append(page_data)
        
        # Save after each URL
        with open('enhanced_scrape_results.json', 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        
        # Respect rate limiting
        time.sleep(int(os.getenv('SCRAPE_DELAY', 2)))
    
    logger.info("✓ Scraping completed!")

if __name__ == "__main__":
    main() 