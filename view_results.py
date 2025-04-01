import streamlit as st
import json
from PIL import Image
import pandas as pd
from pathlib import Path
import plotly.express as px

def load_data():
    """Load scraping results and screenshot metadata."""
    with open('enhanced_scrape_results.json', 'r', encoding='utf-8') as f:
        return json.load(f)

def display_screenshots(screenshots, url):
    """Display screenshots in a tabbed interface."""
    if not screenshots:
        st.warning("No screenshots available for this URL")
        return

    # Create tabs for different device sizes
    tabs = st.tabs(list(screenshots.keys()))
    for tab, (device, data) in zip(tabs, screenshots.items()):
        with tab:
            try:
                image = Image.open(data['path'])
                st.image(image, caption=f"{device} - {data['resolution']['width']}x{data['resolution']['height']}")
            except Exception as e:
                st.error(f"Error loading screenshot: {str(e)}")

def display_metadata(metadata):
    """Display page metadata in an organized way."""
    st.subheader("📝 Metadata")
    cols = st.columns(2)
    
    with cols[0]:
        st.write("Basic Information")
        st.write(f"Title: {metadata.get('title', 'N/A')}")
        st.write(f"Description: {metadata.get('meta_description', 'N/A')}")
        st.write(f"Robots: {metadata.get('meta_robots', 'N/A')}")
    
    with cols[1]:
        st.write("Technical Details")
        st.write(f"Canonical: {metadata.get('canonical', 'N/A')}")
        st.write(f"Viewport: {metadata.get('viewport', 'N/A')}")
        
        if metadata.get('hreflang'):
            st.write("Hreflang Tags:")
            for tag in metadata['hreflang']:
                st.write(f"- {tag['lang']}: {tag['href']}")

def display_content_analysis(content):
    """Display content analysis with visualizations."""
    st.subheader("📊 Content Analysis")
    
    # Word count visualization
    st.metric("Total Word Count", content['word_count'])
    
    # Display clean text sample
    with st.expander("View Clean Text Sample"):
        st.write(content['clean_text'][:500] + "...")

def display_headings(headings):
    """Display heading structure with hierarchy visualization."""
    st.subheader("📑 Heading Structure")
    
    # Convert headings to DataFrame for visualization
    df = pd.DataFrame(headings)  # headings should already be a list of dicts
    if not df.empty:
        fig = px.treemap(df, 
                        path=['level', 'text'],
                        values='word_count',
                        title='Heading Hierarchy')
        st.plotly_chart(fig)

def display_images(images):
    """Display image analysis with thumbnails."""
    st.subheader("🖼️ Images")
    
    # Create a DataFrame for easy filtering
    df = pd.DataFrame(images)  # images should already be a list of dicts
    if not df.empty:
        # Summary metrics
        cols = st.columns(4)
        cols[0].metric("Total Images", len(df))
        cols[1].metric("Images with Alt Text", len(df[df['alt'].str.len() > 0]))
        cols[2].metric("Average Width", int(df['width'].mean()) if 'width' in df else 'N/A')
        cols[3].metric("Average Height", int(df['height'].mean()) if 'height' in df else 'N/A')
        
        # Image gallery
        with st.expander("View Image Gallery"):
            for idx, row in df.iterrows():
                st.write(f"Image {idx + 1}")
                st.write(f"URL: {row['url']}")
                st.write(f"Alt: {row['alt']}")
                st.write(f"Size: {row['width']}x{row['height']}")
                st.write("---")

def display_links(links):
    """Display link analysis with network visualization."""
    st.subheader("🔗 Links")
    
    # Convert links to DataFrame
    df = pd.DataFrame(links)  # links should already be a list of dicts
    if not df.empty:
        # Summary metrics
        cols = st.columns(3)
        cols[0].metric("Total Links", len(df))
        cols[1].metric("Internal Links", len(df[df['is_internal']]))
        cols[2].metric("External Links", len(df[~df['is_internal']]))
        
        # Link table
        with st.expander("View Link Details"):
            st.dataframe(df[['url', 'anchor_text', 'is_internal', 'is_nofollow']])

def display_structured_data(data):
    """Display structured data in an organized way."""
    st.subheader("🔍 Structured Data")
    
    tabs = st.tabs(['Schema.org', 'Open Graph', 'Twitter Cards', 'Other'])
    
    with tabs[0]:
        st.json(data.get('schema_org', {}))
    with tabs[1]:
        st.json(data.get('open_graph', {}))
    with tabs[2]:
        st.json(data.get('twitter_cards', {}))
    with tabs[3]:
        col1, col2 = st.columns(2)
        with col1:
            st.write("Microdata")
            st.json(data.get('microdata', {}))
        with col2:
            st.write("RDFa")
            st.json(data.get('rdfa', {}))

def main():
    st.set_page_config(
        page_title="Web Scraping Results",
        page_icon="🔍",
        layout="wide"
    )
    
    st.title("🌐 Web Scraping Analysis Dashboard")
    
    # Load data
    try:
        data = load_data()
        
        # URL selector
        urls = [page['url'] for page in data['pages']]
        selected_url = st.selectbox("Select URL to analyze", urls)
        
        # Get selected page data
        page_data = next(page for page in data['pages'] if page['url'] == selected_url)
        
        # Display timestamp and status
        st.write(f"Scraped at: {page_data['scrape_timestamp']}")
        if page_data['status']['success']:
            st.success("Successfully scraped")
        else:
            st.error(f"Scraping failed: {page_data['status']['message']}")
            return
        
        # Create tabs for different aspects
        tabs = st.tabs(["Screenshots", "Content", "Technical"])
        
        with tabs[0]:
            display_screenshots(page_data.get('screenshots', {}), selected_url)
        
        with tabs[1]:
            display_metadata(page_data['metadata'])
            display_content_analysis(page_data['content'])
            display_headings(page_data['headings'])
            display_images(page_data['images'])
            display_links(page_data['links'])
        
        with tabs[2]:
            display_structured_data(page_data['structured_data'])
            
            # Technical metrics
            st.subheader("⚙️ Technical Metrics")
            tech_data = page_data['technical']
            cols = st.columns(4)
            cols[0].metric("Load Time", f"{tech_data['load_time']:.2f}s")
            cols[1].metric("Page Size", f"{tech_data['page_size'] / 1024:.1f}KB")
            cols[2].metric("Status Code", tech_data['status_code'])
            cols[3].metric("Content Type", tech_data['content_type'])
            
            # Scripts and stylesheets
            col1, col2 = st.columns(2)
            with col1:
                st.write("Scripts")
                for script in tech_data['scripts']:
                    st.code(script, language="text")
            with col2:
                st.write("Stylesheets")
                for css in tech_data['stylesheets']:
                    st.code(css, language="text")
        
    except Exception as e:
        st.error(f"Error loading data: {str(e)}")

if __name__ == "__main__":
    main() 