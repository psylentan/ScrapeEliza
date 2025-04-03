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
from openai import OpenAI
import anthropic
import argparse

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
    def __init__(self, enable_analysis=False, enable_screenshots=False):
        self.enable_analysis = enable_analysis
        self.enable_screenshots = enable_screenshots
        if enable_analysis:
            self.anthropic_client = anthropic.Anthropic(
                api_key=os.getenv('ANTHROPIC_API_KEY')
            )
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        self.base_url = None
        self.session = requests.Session()
        if enable_screenshots:
            self.screenshot_manager = ScreenshotManager()
        else:
            self.screenshot_manager = None
    
    def analyze_content(self, url: str, content: str) -> Dict:
        """Analyze content using Anthropic's Claude API."""
        try:
            logger.info("Analyzing content with Anthropic's Claude...")
            
            prompt = f"""Analyze this webpage content and provide:
            1. A brief summary (2-3 sentences)
            2. The target audience
            3. Key takeaways (3-5 bullet points)
            4. Content quality score (1-10)
            5. SEO recommendations (if any)

            URL: {url}

            Content:
            {content[:3000]}
            
            Format your response as JSON with the following structure:
            {{
                "summary": "...",
                "target_audience": "...",
                "key_takeaways": ["...", "..."],
                "quality_score": N,
                "seo_recommendations": ["...", "..."]
            }}
            """

            message = self.anthropic_client.messages.create(
                model="claude-3-opus-20240229",
                max_tokens=1000,
                temperature=0,
                system="You are an expert content analyst. Analyze web content and provide insights in JSON format.",
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            
            # Parse the response as JSON
            try:
                analysis = json.loads(message.content[0].text)
                logger.info("✓ Content analyzed successfully")
                return {
                    "raw_analysis": json.dumps(analysis, ensure_ascii=False, indent=2)
                }
            except json.JSONDecodeError:
                return {
                    "raw_analysis": message.content[0].text
                }
            
        except Exception as e:
            logger.error(f"Error during content analysis: {str(e)}")
            return {
                "raw_analysis": f"Analysis failed: {str(e)}"
            }

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
            response = self.session.get(url, headers=self.headers)
            response.raise_for_status()
            html = response.text
            soup = BeautifulSoup(html, 'html.parser')
            self.base_url = get_base_url(html, url)

            # Take screenshots if enabled
            screenshots = {}
            if self.enable_screenshots:
                logger.info("Taking screenshots...")
                screenshots = self.screenshot_manager.take_screenshots(url)

            # Extract metadata and content
            metadata = {
                'title': soup.title.string if soup.title else None,
                'description': soup.find('meta', {'name': 'description'})['content'] if soup.find('meta', {'name': 'description'}) else '',
                'h1': soup.h1.text if soup.h1 else None
            }

            # Extract main content
            main_content = ' '.join([p.text for p in soup.find_all('p')])
            max_length = int(os.getenv('MAX_CONTENT_LENGTH', 2000))
            if len(main_content) > max_length:
                main_content = main_content[:max_length] + '...'

            # Run analysis if enabled
            if self.enable_analysis:
                analysis = self.analyze_content(url, main_content)
            else:
                analysis = {
                    "raw_analysis": "Content analysis not enabled"
                }

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

            # Add screenshots if they were taken
            if screenshots:
                page_data["screenshots"] = screenshots

            logger.info(f"✓ Successfully scraped {url}")
            return page_data

        except Exception as e:
            logger.error(f"✗ Error scraping URL: {str(e)}")
            return {
                "url": url,
                "metadata": {},
                "content": {},
                "scrape_status": {
                    "success": False,
                    "error": str(e),
                    "timestamp": datetime.now().isoformat()
                },
                "analysis": {},
                "screenshots": {}
            }

def main(enable_analysis=False, enable_screenshots=False):
    # Read URLs from file
    with open('urls.txt', 'r', encoding='utf-8') as f:
        urls = [line.strip() for line in f if line.strip()]
    
    scraper = EnhancedWebScraper(enable_analysis=enable_analysis, enable_screenshots=enable_screenshots)
    
    output_file = 'enhanced_scrape_results.json'
    
    # Initialize results
    results = {
        "scrape_timestamp": datetime.now().isoformat(),
        "total_urls_processed": len(urls),
        "pages": []
    }
    
    # Process each URL
    for i, url in enumerate(urls, 1):
        logger.info(f"\nProcessing URL {i} of {len(urls)}")
        page_data = scraper.scrape_url(url)
        results["pages"].append(page_data)
        
        # Save after each URL
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        
        if i < len(urls):
            delay = int(os.getenv('SCRAPE_DELAY', 2))
            logger.info(f"Waiting {delay} seconds before next URL...")
            time.sleep(delay)
    
    logger.info(f"\n✓ Scraping completed! Results saved to {output_file}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Enhanced web scraper with optional features')
    parser.add_argument('--analyze', action='store_true', help='Enable OpenAI content analysis')
    parser.add_argument('--screenshots', action='store_true', help='Enable screenshot capture')
    args = parser.parse_args()
    main(enable_analysis=args.analyze, enable_screenshots=args.screenshots) 