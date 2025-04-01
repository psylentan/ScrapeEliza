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
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        self.base_url = None
        self.session = requests.Session()
        self.screenshot_manager = ScreenshotManager()
    
    def get_image_data(self, img_tag: BeautifulSoup, base_url: str) -> ImageData:
        """Extract comprehensive image data including dimensions and file size."""
        try:
            src = img_tag.get('src', '')
            if not src:
                return None

            # Handle data URLs
            if src.startswith('data:'):
                # Extract dimensions from SVG viewBox if present
                if 'svg' in src.lower():
                    match = re.search(r'viewBox=[\'"]([^\'"]*)[\'"]', src)
                    if match:
                        try:
                            _, _, width, height = map(float, match.group(1).split())
                            return ImageData(
                                url=src[:50] + '...',  # Truncate data URL
                                alt=img_tag.get('alt', ''),
                                title=img_tag.get('title'),
                                width=int(width),
                                height=int(height),
                                file_size=len(src),
                                format='SVG',
                                is_data_url=True
                            )
                        except:
                            pass
                return ImageData(
                    url=src[:50] + '...',  # Truncate data URL
                    alt=img_tag.get('alt', ''),
                    title=img_tag.get('title'),
                    width=None,
                    height=None,
                    file_size=len(src),
                    format=src.split(';')[0].split('/')[1] if ';' in src else None,
                    is_data_url=True
                )

            # Handle regular URLs
            img_url = urljoin(base_url, src)
            response = self.session.get(img_url, stream=True)
            if response.status_code != 200:
                return None

            img = Image.open(BytesIO(response.content))
            
            return ImageData(
                url=img_url,
                alt=img_tag.get('alt', ''),
                title=img_tag.get('title'),
                width=img.width,
                height=img.height,
                file_size=len(response.content),
                format=img.format,
                is_data_url=False
            )
        except Exception as e:
            logger.warning(f"Failed to process image {src}: {str(e)}")
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

    def scrape_url(self, url: str) -> Dict:
        """Enhanced scraping with comprehensive data extraction."""
        try:
            logger.info(f"Scraping: {url}")
            start_time = time.time()
            
            # Take screenshots first
            logger.info("Taking screenshots...")
            screenshots = self.screenshot_manager.take_screenshots(url)
            
            # Fetch page
            response = self.session.get(url, headers=self.headers)
            response.raise_for_status()
            
            # Parse HTML
            soup = BeautifulSoup(response.text, 'html.parser')
            self.base_url = url

            # Basic metadata
            metadata = {
                'title': soup.title.string if soup.title else None,
                'meta_description': soup.find('meta', {'name': 'description'})['content'] if soup.find('meta', {'name': 'description'}) else None,
                'meta_robots': soup.find('meta', {'name': 'robots'})['content'] if soup.find('meta', {'name': 'robots'}) else None,
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
                "screenshots": screenshots
            }

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