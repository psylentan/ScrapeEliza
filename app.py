import streamlit as st
import json
from enhanced_scraper import EnhancedWebScraper
from urllib.parse import urlparse, quote, unquote
import time
from datetime import datetime
import base64
import glob
import os
from typing import List, Dict

st.set_page_config(
    page_title="URL Scraper & Analyzer",
    page_icon="🔍",
    layout="centered"
)

def get_domain(url):
    """Extract domain from URL"""
    try:
        return urlparse(url).netloc.replace('www.', '')
    except:
        return 'unknown'

def get_session_files():
    """Get list of all session files"""
    files = glob.glob('scraped_*.json')
    return sorted(files, reverse=True)

def load_session(filename):
    """Load a specific session file"""
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # Handle both old and new format
            if isinstance(data, list):
                st.session_state.results = {"pages": data}
            else:
                st.session_state.results = data
            st.session_state.current_session = filename
            return True
    except Exception as e:
        st.error(f"Error loading session: {str(e)}")
        return False

# Initialize session state
if 'urls' not in st.session_state:
    st.session_state.urls = []
if 'results' not in st.session_state:
    st.session_state.results = []
if 'is_scraping' not in st.session_state:
    st.session_state.is_scraping = False
if 'current_session' not in st.session_state:
    st.session_state.current_session = None
if 'selected_page' not in st.session_state:
    st.session_state.selected_page = None
if 'results_file' not in st.session_state:
    st.session_state.results_file = None
if 'current_page' not in st.session_state:
    st.session_state.current_page = None

# Auto-load most recent session if no session is loaded
if st.session_state.results is None:
    session_files = get_session_files()
    if session_files:
        most_recent = session_files[0]  # Files are already sorted newest first
        load_session(most_recent)
        st.sidebar.success(f"Automatically loaded most recent session: {most_recent}")

def save_session(urls, results):
    """Save current session with domain-based filename"""
    if not urls or not results:
        return None
    
    # Get domain from first URL
    domain = get_domain(urls[0])
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"scraped_{domain}_{timestamp}.json"
    
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    return filename

def validate_url(url):
    """Validate if the string is a proper URL"""
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except:
        return False

def process_urls(urls_text):
    """Process and validate the URLs from the text input"""
    urls = [url.strip() for url in urls_text.split('\n') if url.strip()]
    valid_urls = []
    invalid_urls = []
    
    for url in urls:
        if validate_url(url):
            valid_urls.append(url)
        else:
            invalid_urls.append(url)
    
    return valid_urls, invalid_urls

def run_scraper(url, take_screenshots=True, analyze_content=True):
    """Run the scraper on a single URL and return results."""
    try:
        scraper = EnhancedWebScraper()
        result = scraper.scrape_url(url, take_screenshots=take_screenshots, analyze_content=analyze_content)
        return result
    except Exception as e:
        return {
            "url": url,
            "error": str(e),
            "status": {"success": False, "error": str(e)}
        }

def encode_url(url):
    """Safely encode URL for query parameter"""
    try:
        # First encode as UTF-8 bytes, then as base64
        return base64.urlsafe_b64encode(url.encode('utf-8')).decode('utf-8')
    except:
        return None

def decode_url(encoded_url):
    """Safely decode URL from query parameter"""
    try:
        # Add padding if needed
        padding = 4 - (len(encoded_url) % 4)
        if padding != 4:
            encoded_url += '=' * padding
        
        # Decode base64 then UTF-8
        return base64.urlsafe_b64decode(encoded_url.encode('utf-8')).decode('utf-8')
    except:
        return None

def show_url_details(page_data):
    """Display detailed information for a single URL"""
    st.title("URL Analysis Details")
    
    # Back button
    if st.button("← Back to List"):
        st.query_params.clear()
        st.rerun()
    
    # URL and basic info
    st.markdown(f"### [{page_data['url']}]({page_data['url']})")
    
    # Status
    status = "✅ Success" if page_data["status"]["success"] else "❌ Failed"
    st.markdown(f"**Status:** {status}")
    
    # Metadata
    with st.expander("📋 Metadata", expanded=True):
        st.markdown(f"**Title:** {page_data['metadata']['title']}")
        if page_data['metadata']['meta_description']:
            st.markdown(f"**Description:** {page_data['metadata']['meta_description']}")
        if page_data['metadata']['meta_robots']:
            st.markdown(f"**Robots:** {page_data['metadata']['meta_robots']}")
        if page_data['metadata']['canonical']:
            st.markdown(f"**Canonical URL:** {page_data['metadata']['canonical']}")
        if page_data['metadata']['viewport']:
            st.markdown(f"**Viewport:** {page_data['metadata']['viewport']}")
        if page_data['headings']:
            st.markdown("**Headings:**")
            for heading in page_data['headings']:
                st.markdown(f"• H{heading['level']}: {heading['text']} ({heading['word_count']} words)")
    
    # Screenshots
    screenshots = page_data.get('screenshots', {})
    if screenshots:
        with st.expander("Screenshots", expanded=True):
            if screenshots.get("status") == "success":
                for name, path in screenshots.get("paths", {}).items():
                    if os.path.exists(path):
                        st.subheader(name.replace("_", " ").title())
                        st.image(path)
                    else:
                        st.warning(f"Screenshot not found: {path}")
            elif screenshots.get("status") == "disabled":
                st.info("Screenshots were disabled for this scrape")
            elif screenshots.get("status") == "failed":
                st.error(f"Screenshots failed: {screenshots.get('error', 'Unknown error')}")
            else:
                st.warning("Screenshot status unknown")
    
    # Content
    with st.expander("📝 Content", expanded=False):
        st.markdown(f"**Word Count:** {page_data['content']['word_count']}")
        st.markdown("**Main Text:**")
        st.markdown(page_data['content']['clean_text'])
    
    # Images
    if page_data.get('images'):
        with st.expander("🖼️ Images", expanded=False):
            for img in page_data['images']:
                st.markdown(f"**Image:** {img['url']}")
                st.markdown(f"• Alt: {img['alt']}")
                if img['title']:
                    st.markdown(f"• Title: {img['title']}")
                if img['width'] and img['height']:
                    st.markdown(f"• Dimensions: {img['width']}x{img['height']}")
                if img['file_size']:
                    st.markdown(f"• Size: {img['file_size']} bytes")
                if img['format']:
                    st.markdown(f"• Format: {img['format']}")
    
    # Links
    if page_data.get('links'):
        with st.expander("🔗 Links", expanded=False):
            internal_links = [link for link in page_data['links'] if link['is_internal']]
            external_links = [link for link in page_data['links'] if not link['is_internal']]
            
            st.markdown(f"**Internal Links ({len(internal_links)}):**")
            for link in internal_links:
                st.markdown(f"• [{link['anchor_text']}]({link['url']})")
                if link['status_code']:
                    st.markdown(f"  Status: {link['status_code']}")
            
            st.markdown(f"**External Links ({len(external_links)}):**")
            for link in external_links:
                st.markdown(f"• [{link['anchor_text']}]({link['url']})")
                if link['is_nofollow']:
                    st.markdown("  (nofollow)")
    
    # Technical Data
    if page_data.get('technical'):
        with st.expander("⚙️ Technical Data", expanded=False):
            tech = page_data['technical']
            st.markdown(f"**Load Time:** {tech['load_time']:.2f} seconds")
            st.markdown(f"**Page Size:** {tech['page_size']:,} bytes")
            st.markdown(f"**Status Code:** {tech['status_code']}")
            st.markdown(f"**Content Type:** {tech['content_type']}")
            
            if tech['scripts']:
                st.markdown("**Scripts:**")
                for script in tech['scripts']:
                    st.markdown(f"• {script}")
            
            if tech['stylesheets']:
                st.markdown("**Stylesheets:**")
                for css in tech['stylesheets']:
                    st.markdown(f"• {css}")
    
    # Structured Data
    if page_data.get('structured_data'):
        with st.expander("🔍 Structured Data", expanded=False):
            struct_data = page_data['structured_data']
            if struct_data.get('schema_org'):
                st.markdown("**Schema.org:**")
                st.json(struct_data['schema_org'])
            if struct_data.get('open_graph'):
                st.markdown("**Open Graph:**")
                st.json(struct_data['open_graph'])
            if struct_data.get('twitter_cards'):
                st.markdown("**Twitter Cards:**")
                st.json(struct_data['twitter_cards'])
    
    # Analysis
    if page_data["analysis"].get("raw_analysis"):
        with st.expander("🤖 AI Analysis", expanded=True):
            try:
                analysis_data = json.loads(page_data["analysis"]["raw_analysis"])
                
                # Summary
                if analysis_data.get("summary"):
                    st.markdown("**Summary:**")
                    st.markdown(analysis_data["summary"])
                
                # Target Audience
                if analysis_data.get("target_audience"):
                    st.markdown("**Target Audience:**")
                    st.markdown(analysis_data["target_audience"])
                
                # Key Takeaways
                if analysis_data.get("key_takeaways"):
                    st.markdown("**Key Takeaways:**")
                    for takeaway in analysis_data["key_takeaways"]:
                        st.markdown(f"• {takeaway}")
            except json.JSONDecodeError:
                st.markdown(page_data["analysis"]["raw_analysis"])

def show_page_details(page_data):
    """Display detailed information about a scraped page."""
    if not page_data:
        st.warning("No page data selected")
        return

    # URL and basic info
    st.header("Page Details")
    url = page_data.get("url", "")
    st.markdown(f"🔗 **URL**: [{url}]({url})")
    
    # Status information
    status = page_data.get("status", {})
    if status:
        with st.expander("Status Information", expanded=True):
            st.write("Success:", status.get("success", False))
            st.write("Status Code:", status.get("status_code"))
            st.write("Response Time:", f'{status.get("response_time", 0):.2f}s')
            if status.get("error"):
                st.error(f"Error: {status['error']}")

    # Metadata
    metadata = page_data.get("metadata", {})
    if metadata:
        with st.expander("Metadata", expanded=True):
            st.write("Title:", metadata.get("title"))
            st.write("Description:", metadata.get("description"))
            st.write("Keywords:", metadata.get("keywords"))
            st.write("Author:", metadata.get("author"))
            st.write("Robots:", metadata.get("robots"))
            st.write("Language:", metadata.get("language"))
            st.write("Canonical:", metadata.get("canonical"))
            st.write("Viewport:", metadata.get("viewport"))
            
            if metadata.get("hreflang"):
                st.write("Hreflang Tags:")
                for tag in metadata["hreflang"]:
                    st.write(f"- {tag['lang']}: {tag['href']}")

    # Technical Data
    tech_data = page_data.get("technical", {})
    if tech_data:
        with st.expander("Technical Data", expanded=True):
            st.write("Content Type:", tech_data.get("content_type"))
            st.write("Page Size:", f"{tech_data.get('page_size', 0) / 1024:.2f} KB")
            st.write("Load Time:", f"{tech_data.get('load_time', 0):.2f}s")
            if tech_data.get("scripts"):
                st.write("Scripts:")
                for script in tech_data["scripts"]:
                    st.write(f"- {script}")
            if tech_data.get("stylesheets"):
                st.write("Stylesheets:")
                for css in tech_data["stylesheets"]:
                    st.write(f"- {css}")

    # Screenshots
    screenshots = page_data.get("screenshots", {})
    if screenshots:
        with st.expander("Screenshots", expanded=True):
            if screenshots.get("status") == "success":
                for name, path in screenshots.get("paths", {}).items():
                    if os.path.exists(path):
                        st.subheader(name.replace("_", " ").title())
                        st.image(path)
                    else:
                        st.warning(f"Screenshot not found: {path}")
            elif screenshots.get("status") == "disabled":
                st.info("Screenshots were disabled for this scrape")
            elif screenshots.get("status") == "failed":
                st.error(f"Screenshots failed: {screenshots.get('error', 'Unknown error')}")
            else:
                st.warning("Screenshot status unknown")

    # Images
    images = page_data.get("images", [])
    if images:
        with st.expander("Images", expanded=True):
            for img in images:
                st.write("Source:", img.get("url"))
                st.write("Alt Text:", img.get("alt"))
                if img.get("title"):
                    st.write("Title:", img.get("title"))
                if img.get("width") and img.get("height"):
                    st.write(f"Dimensions: {img.get('width')}x{img.get('height')}")
                if img.get("file_size"):
                    st.write(f"Size: {img.get('file_size') / 1024:.2f} KB")
                if img.get("format"):
                    st.write("Format:", img.get("format"))
                st.write("---")

    # Links
    links = page_data.get("links", [])
    if links:
        with st.expander("Links", expanded=True):
            internal_links = [link for link in links if link.get("is_internal")]
            external_links = [link for link in links if not link.get("is_internal")]
            
            if internal_links:
                st.subheader("Internal Links")
                for link in internal_links:
                    st.write(f"URL: {link.get('url')}")
                    st.write(f"Anchor Text: {link.get('anchor_text')}")
                    st.write(f"Nofollow: {link.get('is_nofollow', False)}")
                    st.write(f"Status: {link.get('status_code')}")
                    st.write("---")
            
            if external_links:
                st.subheader("External Links")
                for link in external_links:
                    st.write(f"URL: {link.get('url')}")
                    st.write(f"Anchor Text: {link.get('anchor_text')}")
                    st.write(f"Nofollow: {link.get('is_nofollow', False)}")
                    st.write(f"Status: {link.get('status_code')}")
                    st.write("---")

    # Content
    content = page_data.get("content", {})
    if content:
        with st.expander("Content", expanded=True):
            st.write("Word Count:", content.get("word_count"))
            st.write("Clean Text:")
            st.write(content.get("clean_text"))

    # Structured Data
    structured_data = page_data.get("structured_data", {})
    if structured_data:
        with st.expander("Structured Data", expanded=True):
            if structured_data.get("schema_org"):
                st.subheader("Schema.org")
                st.json(structured_data["schema_org"])
            if structured_data.get("open_graph"):
                st.subheader("Open Graph")
                st.json(structured_data["open_graph"])
            if structured_data.get("twitter_cards"):
                st.subheader("Twitter Cards")
                st.json(structured_data["twitter_cards"])
            if structured_data.get("microdata"):
                st.subheader("Microdata")
                st.json(structured_data["microdata"])
            if structured_data.get("rdfa"):
                st.subheader("RDFa")
                st.json(structured_data["rdfa"])
            if structured_data.get("json_ld"):
                st.subheader("JSON-LD")
                st.json(structured_data["json_ld"])

    # Headings
    headings = page_data.get("headings", [])
    if headings:
        with st.expander("Headings", expanded=True):
            for heading in headings:
                st.write(f"**H{heading.get('level')}**: {heading.get('text')}")
                st.write(f"Word Count: {heading.get('word_count')}")
                st.write("---")

    # Analysis
    analysis = page_data.get("analysis", {})
    if analysis:
        with st.expander("AI Analysis", expanded=True):
            if analysis.get("raw_analysis"):
                st.write(analysis["raw_analysis"])
            if analysis.get("status") == "failed":
                st.error(f"Analysis failed: {analysis.get('error', 'Unknown error')}")
            elif analysis.get("status") == "timeout":
                st.warning("Analysis timed out")

def save_scrape_results(results: List[Dict], domain: str):
    """Save scrape results to a JSON file with timestamp."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"scrape_results_{domain}_{timestamp}.json"
    
    # Create results directory if it doesn't exist
    os.makedirs("scrape_results", exist_ok=True)
    filepath = os.path.join("scrape_results", filename)
    
    # Save results
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    return filepath

def get_most_recent_scrape():
    """Get the most recent scrape results file."""
    results_dir = "scrape_results"
    if not os.path.exists(results_dir):
        return None
        
    # Get all JSON files in the results directory
    json_files = [f for f in os.listdir(results_dir) if f.endswith('.json')]
    if not json_files:
        return None
        
    # Sort by modification time, newest first
    latest_file = max(json_files, key=lambda x: os.path.getmtime(os.path.join(results_dir, x)))
    return os.path.join(results_dir, latest_file)

def load_scrape_results(filepath: str) -> List[Dict]:
    """Load scrape results from a JSON file."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        st.error(f"Error loading results: {str(e)}")
        return []

# Main UI Logic
query_params = st.query_params

# Initialize session state
if 'results' not in st.session_state:
    st.session_state.results = []
if 'results_file' not in st.session_state:
    st.session_state.results_file = None
if 'current_page' not in st.session_state:
    st.session_state.current_page = None

# Load most recent scrape if available
if not st.session_state.results:
    latest_file = get_most_recent_scrape()
    if latest_file:
        st.session_state.results = load_scrape_results(latest_file)
        st.session_state.results_file = latest_file
        st.info(f"Loaded most recent scrape from: {latest_file}")

# Sidebar for loading previous scrapes
with st.sidebar:
    st.header("Previous Scrapes")
    results_dir = "scrape_results"
    if os.path.exists(results_dir):
        json_files = [f for f in os.listdir(results_dir) if f.endswith('.json')]
        if json_files:
            # Sort by modification time, newest first
            json_files.sort(key=lambda x: os.path.getmtime(os.path.join(results_dir, x)), reverse=True)
            
            for file in json_files:
                filepath = os.path.join(results_dir, file)
                if st.button(f"Load: {file}", key=f"load_{file}"):
                    st.session_state.results = load_scrape_results(filepath)
                    st.session_state.results_file = filepath
                    st.success(f"Loaded scrape from: {file}")
        else:
            st.info("No previous scrapes found")
    else:
        st.info("No previous scrapes found")

# Main content area
st.title("Web Scraper")

# URL input section
with st.expander("Enter URLs to Scrape", expanded=True):
    urls_input = st.text_area(
        "Enter URLs (one per line):",
        value="",
        height=150,
        help="Enter one URL per line. The scraper will process each URL in sequence."
    )
    
    col1, col2 = st.columns([1, 4])
    with col1:
        process_button = st.button("Process URLs")
    with col2:
        if process_button:
            urls = [url.strip() for url in urls_input.split('\n') if url.strip()]
            if urls:
                st.success(f"Found {len(urls)} valid URLs to process")
            else:
                st.warning("No valid URLs found")

# Scraping options
with st.expander("Scraping Options", expanded=True):
    take_screenshots = st.checkbox("Take Screenshots", value=True)
    analyze_content = st.checkbox("Analyze Content", value=True)
    
    if st.button("Start Scraping", disabled=not urls_input.strip()):
        with st.spinner("Scraping in progress..."):
            # Process URLs
            urls = [url.strip() for url in urls_input.split('\n') if url.strip()]
            if not urls:
                st.warning("No valid URLs to process")
            else:
                results = []
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                for i, url in enumerate(urls):
                    try:
                        status_text.text(f"Processing: {url}")
                        progress_bar.progress((i + 1) / len(urls))
                        
                        result = run_scraper(url, take_screenshots, analyze_content)
                        results.append(result)
                    except Exception as e:
                        st.error(f"Error processing {url}: {str(e)}")
                        results.append({
                            "url": url,
                            "error": str(e),
                            "status": {"success": False, "error": str(e)}
                        })
                
                # Update session state with results
                st.session_state.results = results
                
                # Save results
                if results:
                    domain = urlparse(results[0]["url"]).netloc
                    results_file = save_scrape_results(results, domain)
                    st.session_state.results_file = results_file
                    st.success(f"Results saved to: {results_file}")
                
                status_text.text("Scraping completed!")
                progress_bar.progress(1.0)

# Display results
if st.session_state.results:
    st.header("Scraping Results")
    
    # Search box
    search_query = st.text_input("Search results:", "")
    
    # Filter results based on search
    filtered_results = st.session_state.results
    if search_query:
        filtered_results = [
            result for result in st.session_state.results
            if search_query.lower() in result.get("url", "").lower() or
               search_query.lower() in result.get("metadata", {}).get("title", "").lower() or
               search_query.lower() in result.get("metadata", {}).get("description", "").lower()
        ]
    
    # Display results in a list
    for result in filtered_results:
        with st.container():
            col1, col2 = st.columns([3, 1])
            with col1:
                url = result.get("url", "No URL")
                title = result.get("metadata", {}).get("title", "No Title")
                st.markdown(f"**{title}**")
                st.markdown(f"🔗 [{url}]({url})")
            with col2:
                if st.button("View Details", key=f"view_{url}"):
                    st.session_state.selected_page = result

# Display selected page details
if st.session_state.get('selected_page'):
    show_page_details(st.session_state.selected_page) 