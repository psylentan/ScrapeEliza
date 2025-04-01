import streamlit as st
import json
from enhanced_scraper import EnhancedWebScraper
from urllib.parse import urlparse, quote, unquote
import time
from datetime import datetime
import base64
import glob
import os

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
    st.session_state.results = None
if 'is_scraping' not in st.session_state:
    st.session_state.is_scraping = False
if 'current_session' not in st.session_state:
    st.session_state.current_session = None

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

def run_scraper(urls, progress_bar, status_text, take_screenshots=True):
    """Run the scraper on a list of URLs and return results."""
    results = []
    scraper = EnhancedWebScraper()
    
    # Get domain from first URL for the filename
    domain = urlparse(urls[0]).netloc.replace('www.', '')
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    results_file = f'scraped_{domain}_{timestamp}.json'
    
    for i, url in enumerate(urls):
        try:
            progress_bar.progress((i) / len(urls))
            status_text.text(f'Scraping {url}...')
            
            page_data = scraper.scrape_url(url, take_screenshots=take_screenshots)
            results.append(page_data)
            
            # Save results after each successful scrape
            with open(results_file, 'w', encoding='utf-8') as f:
                json.dump({"pages": results}, f, indent=2, ensure_ascii=False)
            
        except Exception as e:
            st.error(f'Error scraping {url}: {str(e)}')
    
    progress_bar.progress(1.0)
    status_text.text('Scraping completed!')
    return {"pages": results}, results_file

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
    if page_data.get('screenshots'):
        with st.expander("📸 Screenshots", expanded=True):
            screenshots = page_data['screenshots']
            if isinstance(screenshots, dict):
                if 'status' in screenshots:
                    if screenshots['status'] == 'disabled':
                        st.info(screenshots.get('message', 'Screenshots were disabled for this scrape'))
                    elif screenshots['status'] == 'failed':
                        st.error(f"Screenshot error: {screenshots.get('message', 'Unknown error')}")
                    else:
                        # Display actual screenshots
                        for view, screenshot in screenshots.items():
                            if screenshot and isinstance(screenshot, str):
                                st.markdown(f"**{view.title()} View:**")
                                st.image(screenshot)
            else:
                st.error("Invalid screenshot data format")
    
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
            st.write("Response Time:", f"{status.get('response_time', 0):.2f}s")
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
    tech_data = page_data.get("technical_data", {})
    if tech_data:
        with st.expander("Technical Data", expanded=True):
            st.write("Content Type:", tech_data.get("content_type"))
            st.write("Charset:", tech_data.get("charset"))
            st.write("Page Size:", f"{tech_data.get('page_size', 0) / 1024:.2f} KB")
            st.write("Load Time:", f"{tech_data.get('load_time', 0):.2f}s")

    # Screenshots
    screenshots = page_data.get("screenshots", {})
    if screenshots:
        with st.expander("Screenshots", expanded=True):
            for name, path in screenshots.items():
                if os.path.exists(path):
                    st.subheader(name.replace("_", " ").title())
                    st.image(path)
                else:
                    st.warning(f"Screenshot not found: {path}")

    # Images
    images = page_data.get("images", [])
    if images:
        with st.expander("Images", expanded=True):
            for img in images:
                st.write("Source:", img.get("src"))
                st.write("Alt Text:", img.get("alt"))
                st.write("Size:", img.get("size"))
                st.write("---")

    # Links
    links = page_data.get("links", {})
    if links:
        with st.expander("Links", expanded=True):
            if links.get("internal"):
                st.subheader("Internal Links")
                for link in links["internal"]:
                    st.write(link)
            if links.get("external"):
                st.subheader("External Links")
                for link in links["external"]:
                    st.write(link)

    # Main Content
    content = page_data.get("main_content")
    if content:
        with st.expander("Main Content", expanded=True):
            st.markdown(content)

    # Raw HTML (for debugging)
    html = page_data.get("html")
    if html:
        with st.expander("Raw HTML", expanded=False):
            st.code(html, language="html")

# Main UI Logic
query_params = st.query_params

# Display debug info in sidebar
if 'results' in st.session_state:
    st.sidebar.write("Debug Info:")
    st.sidebar.write(f"\nNumber of pages in results: {len(st.session_state.results)}")
    
    # Get URL from query parameters if available
    url_param = st.query_params.get('url', None)
    if url_param:
        st.sidebar.write(f"\nSelected URL param: {url_param}")
        decoded_url = decode_url(url_param)
        st.sidebar.write(f"\nDecoded URL: {decoded_url}")
        
        # Check if URL exists in results
        urls_in_results = [page['url'] for page in st.session_state.results]
        if decoded_url not in urls_in_results:
            st.sidebar.write("\nDebug: URL not found in results")
            st.sidebar.write(f"\nLooking for: {decoded_url}")
            st.sidebar.write("\nAvailable URLs:")
            st.sidebar.json([page['url'] for page in st.session_state.results])
            st.sidebar.write(f"URL not found in results: {decoded_url}")
        else:
            page_data = next(page for page in st.session_state.results if page['url'] == decoded_url)
            show_url_details(page_data)

# Main list view
st.title("Scraped Pages")

if 'results' in st.session_state and st.session_state.results:
    # Get pages from results
    results = st.session_state.results
    if isinstance(results, dict):
        pages = results.get("pages", [])
    else:
        pages = results if isinstance(results, list) else []
    
    # Create columns for the list
    for page in pages:
        with st.container():
            col1, col2 = st.columns([3, 1])
            with col1:
                # Handle both string and dictionary page objects
                if isinstance(page, dict):
                    title = page.get('metadata', {}).get('title') or page.get('url', 'No Title')
                    desc = page.get('metadata', {}).get('description', 'No description available')
                else:
                    title = str(page)
                    desc = "No description available"
                    
                st.markdown(f"### {title}")
                st.write(desc)
            with col2:
                if st.button("View Details", key=f"view_{title}"):
                    st.session_state.selected_page = page
            st.divider()
else:
    st.info("No pages have been scraped yet. Use the sidebar to start scraping.")

# Session Management
st.sidebar.header("Session Management")

# Session selector
session_files = get_session_files()
if session_files:
    selected_session = st.sidebar.selectbox(
        "Load Previous Session",
        session_files,
        index=None,
        placeholder="Choose a session...",
        format_func=lambda x: x.replace('scraped_', '').replace('.json', '').replace('_', ' ')
    )
    
    if selected_session and selected_session != st.session_state.current_session:
        if load_session(selected_session):
            st.sidebar.success(f"Loaded session: {selected_session}")

# Show current session
if st.session_state.current_session:
    st.sidebar.info(f"Current session: {st.session_state.current_session}")

# File Upload Section
st.subheader("Load Existing Results")
uploaded_file = st.file_uploader("Upload JSON results file", type=['json'])

if uploaded_file:
    try:
        json_data = json.load(uploaded_file)
        st.session_state.results = json_data
        st.success(f"Loaded {len(json_data['pages'])} scraped pages from file")
    except Exception as e:
        st.error(f"Error loading JSON file: {str(e)}")

# URL Input
st.subheader("Input URLs")
urls_text = st.text_area(
    "Enter URLs (one per line)",
    height=150,
    help="Enter the URLs you want to scrape, one per line"
)

# Process URLs button
if st.button("Process URLs", disabled=st.session_state.is_scraping):
    valid_urls, invalid_urls = process_urls(urls_text)
    st.session_state.urls = valid_urls
    
    if invalid_urls:
        st.error(f"Found {len(invalid_urls)} invalid URLs:\n" + "\n".join(invalid_urls))
    
    if valid_urls:
        st.success(f"Loaded {len(valid_urls)} valid URLs")

# Display number of loaded URLs
if st.session_state.urls:
    st.info(f"URLs loaded: {len(st.session_state.urls)}")

# Scraping section
if st.session_state.urls:
    st.subheader("Scraping")
    
    # Add screenshot option checkbox
    take_screenshots = st.checkbox("Take screenshots", value=True, help="Enable to capture screenshots of pages (takes longer)")
    
    if st.button("Start Scraping", disabled=st.session_state.is_scraping):
        st.session_state.is_scraping = True
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        try:
            results, results_file = run_scraper(st.session_state.urls, progress_bar, status_text, take_screenshots)
            st.session_state.results = results  # Update results in session state
            st.success("Scraping completed successfully!")
            st.rerun()  # Force a rerun to ensure the UI updates properly
        except Exception as e:
            st.error(f"An error occurred: {str(e)}")
        finally:
            st.session_state.is_scraping = False

# Results section
if st.session_state.results:
    st.subheader("Results")
    
    # Quick search
    search = st.text_input("🔍 Quick search in titles", key="quick_search")
    
    # Get pages from results
    results = st.session_state.results
    if isinstance(results, dict):
        pages = results.get("pages", [])
    else:
        pages = results if isinstance(results, list) else []
        
    # Filter pages based on search
    if search:
        search = search.lower()
        filtered_pages = []
        for page in pages:
            if isinstance(page, dict):
                title = page.get("metadata", {}).get("title", "") or page.get("url", "")
            else:
                title = str(page)
            if search in title.lower():
                filtered_pages.append(page)
        st.info(f"Found {len(filtered_pages)} matching results")
    else:
        filtered_pages = pages
    
    # Display list of titles with links to detail pages
    for page in filtered_pages:
        if isinstance(page, dict):
            title = page.get("metadata", {}).get("title", "") or page.get("url", "")
            status = page.get("status", {})
            success = status.get("success", False) if isinstance(status, dict) else False
            status_emoji = "✅" if success else "❌"
        else:
            title = str(page)
            status_emoji = "❓"
        
        # Create a clickable link with the title
        if st.button(f"{status_emoji} {title}", key=f"btn_{title}"):
            st.session_state.selected_page = page
    
    # Simple download button
    st.download_button(
        label="📥 Download JSON",
        data=json.dumps(st.session_state.results, ensure_ascii=False, indent=2),
        file_name=f"scraped_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
        mime="application/json"
    )

# Display selected page details
if st.session_state.get('selected_page'):
    show_page_details(st.session_state.selected_page) 