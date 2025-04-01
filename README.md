# URL Scraper & Analyzer 🔍

A powerful web scraping and content analysis tool built with Streamlit and OpenAI. This tool allows you to scrape websites, analyze their content using AI, and manage multiple scraping sessions.

## Features

- 🌐 **Web Scraping**: Scrape multiple URLs with metadata extraction
- 🤖 **AI Analysis**: Analyze content using OpenAI's API
- 📊 **Session Management**: Organize scraping sessions by domain
- 🔍 **Search & Filter**: Quick search through scraped content
- 📱 **Responsive UI**: Clean, modern interface with detailed views
- 💾 **Data Export**: Download results in JSON format

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/url-scraper-analyzer.git
cd url-scraper-analyzer
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set up your OpenAI API key:
```bash
# Create a .env file and add your API key
echo "OPENAI_API_KEY=your-api-key-here" > .env
```

## Usage

1. Start the application:
```bash
streamlit run app.py
```

2. Enter URLs to scrape (one per line)
3. Click "Process URLs" to validate the URLs
4. Click "Start Scraping" to begin the scraping process
5. View results and analyze content
6. Switch between different scraping sessions using the sidebar

## Configuration

- `OPENAI_API_KEY`: Your OpenAI API key (required)
- `SCRAPE_DELAY`: Delay between scraping requests (default: 2 seconds)
- `MAX_CONTENT_LENGTH`: Maximum content length for analysis (default: 2000 characters)

## Project Structure

```
url-scraper-analyzer/
├── app.py              # Main Streamlit application
├── scraper.py          # Web scraping functionality
├── requirements.txt    # Python dependencies
├── .env               # Environment variables
├── .gitignore         # Git ignore file
└── scraped_*.json     # Scraping session files
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

MIT License - feel free to use this project for any purpose.

## Acknowledgments

- Built with Streamlit
- Powered by OpenAI
- Beautiful Soup for web scraping 