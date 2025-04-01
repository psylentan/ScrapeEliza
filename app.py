import streamlit as st
import json
from scraper import WebScraper
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

def run_scraper(urls, progress_bar, status_text):
    """Run the scraper with progress updates"""
    scraper = WebScraper()
    
    # Initialize new results
    results = {
        "scrape_timestamp": datetime.now().isoformat(),
        "total_urls_processed": len(urls),
        "pages": []
    }
    
    for i, url in enumerate(urls, 1):
        status_text.text(f"Scraping: {url}")
        progress_bar.progress(i/len(urls))
        
        page_data = scraper.scrape_url(url)
        results["pages"].append(page_data)
        
        if i < len(urls):
            time.sleep(2)
    
    # Save session and update session state
    filename = save_session(urls, results)
    if filename:
        st.session_state.current_session = filename
        st.session_state.results = results  # Make sure to update results in session state
    
    return results

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
    status = "✅ Success" if page_data["scrape_status"]["success"] else "❌ Failed"
    st.markdown(f"**Status:** {status}")
    
    # Metadata
    with st.expander("📋 Metadata", expanded=True):
        st.markdown(f"**Title:** {page_data['metadata']['title']}")
        if page_data['metadata']['description']:
            st.markdown(f"**Description:** {page_data['metadata']['description']}")
        if page_data['metadata']['h1']:
            st.markdown(f"**H1:** {page_data['metadata']['h1']}")
    
    # Content
    with st.expander("📝 Content", expanded=False):
        st.markdown(f"**Word Count:** {page_data['content']['word_count']}")
        st.markdown("**Main Text:**")
        st.markdown(page_data['content']['main_text'])
    
    # Analysis
    if page_data["analysis"].get("raw_analysis"):
        with st.expander("🔍 Analysis", expanded=True):
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

# Main UI Logic
query_params = st.query_params

# Debug information
if st.session_state.results:
    st.sidebar.write("Debug Info:")
    st.sidebar.write(f"Number of pages in results: {len(st.session_state.results['pages'])}")
    if "url" in query_params:
        st.sidebar.write(f"Selected URL param: {query_params['url']}")
        decoded_url = decode_url(query_params["url"])
        st.sidebar.write(f"Decoded URL: {decoded_url}")

# If a specific URL is selected, show its details
if "url" in query_params:
    selected_url = decode_url(query_params["url"])
    if selected_url and st.session_state.results:
        found = False
        for page in st.session_state.results["pages"]:
            if page["url"] == selected_url:
                show_url_details(page)
                found = True
                st.stop()
        
        if not found:
            st.error(f"URL not found in results: {selected_url}")
            st.sidebar.error("Debug: URL not found in results")
            st.sidebar.write("Looking for:", selected_url)
            st.sidebar.write("Available URLs:", [p["url"] for p in st.session_state.results["pages"]])
    else:
        if not selected_url:
            st.error("Failed to decode URL parameter")
        elif not st.session_state.results:
            st.error("No results loaded")
        
    if st.button("← Back to List"):
        st.query_params.clear()
        st.rerun()
    st.stop()

# Main list view
st.title("URL Scraper & Analyzer 🔍")

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
    
    if st.button("Start Scraping", disabled=st.session_state.is_scraping):
        st.session_state.is_scraping = True
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        try:
            results = run_scraper(st.session_state.urls, progress_bar, status_text)
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
    
    # Filter pages based on search
    filtered_pages = st.session_state.results["pages"]
    if search:
        search = search.lower()
        filtered_pages = [
            page for page in filtered_pages
            if search in (page["metadata"]["title"] or page["url"]).lower()
        ]
        st.info(f"Found {len(filtered_pages)} matching results")
    
    # Display list of titles with links to detail pages
    for page in filtered_pages:
        title = page["metadata"]["title"] or page["url"]
        status_emoji = "✅" if page["scrape_status"]["success"] else "❌"
        
        col1, col2 = st.columns([4, 1])
        with col1:
            # Create a link that sets the URL query parameter with proper encoding
            encoded_url = encode_url(page['url'])
            if encoded_url:
                st.markdown(f"• [{title}](?url={encoded_url})")
            else:
                st.markdown(f"• {title} (URL encoding error)")
        with col2:
            st.markdown(f"{status_emoji}")
    
    # Simple download button
    st.download_button(
        label="📥 Download JSON",
        data=json.dumps(st.session_state.results, ensure_ascii=False, indent=2),
        file_name=f"scraped_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
        mime="application/json"
    ) 