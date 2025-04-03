from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import os
from datetime import datetime
import json
from pathlib import Path

class ScreenshotManager:
    # Common device resolutions
    RESOLUTIONS = {
        'desktop_1920': (1920, 1080),
        'desktop_1440': (1440, 900),
        'laptop_1366': (1366, 768),
        'tablet_1024': (1024, 768),
        'mobile_375': (375, 812),  # iPhone X
        'mobile_360': (360, 640),  # Common Android
    }

    def __init__(self, output_dir="screenshots"):
        self.output_dir = output_dir
        self.chrome_options = Options()
        self.chrome_options.add_argument("--headless")  # Run in headless mode
        self.chrome_options.add_argument("--no-sandbox")
        self.chrome_options.add_argument("--disable-dev-shm-usage")
        
        # Create output directory if it doesn't exist
        Path(output_dir).mkdir(parents=True, exist_ok=True)

    def take_screenshots(self, url: str) -> dict:
        """Take screenshots of a URL at different resolutions."""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            domain = url.replace("https://", "").replace("http://", "").split("/")[0]
            
            driver = webdriver.Chrome(options=self.chrome_options)
            paths = {}
            
            try:
                for device, (width, height) in self.RESOLUTIONS.items():
                    # Set window size
                    driver.set_window_size(width, height)
                    
                    # Navigate to URL
                    driver.get(url)
                    
                    # Wait for page to load
                    WebDriverWait(driver, 10).until(
                        lambda driver: driver.execute_script('return document.readyState') == 'complete'
                    )
                    
                    # Additional wait for dynamic content
                    driver.implicitly_wait(2)
                    
                    # Create filename
                    filename = f"{domain}_{device}_{timestamp}.png"
                    filepath = os.path.join(self.output_dir, filename)
                    
                    # Take screenshot of full page
                    total_height = driver.execute_script("return document.body.scrollHeight")
                    driver.set_window_size(width, total_height)
                    driver.save_screenshot(filepath)
                    
                    # Store screenshot path
                    paths[device] = filepath
                    
            finally:
                driver.quit()
            
            return {
                "status": "success",
                "paths": paths,
                "message": f"Successfully captured {len(paths)} screenshots"
            }
            
        except Exception as e:
            return {
                "status": "failed",
                "error": str(e),
                "paths": {}
            }

def main():
    # Test the screenshot manager
    manager = ScreenshotManager()
    with open('urls.txt', 'r') as f:
        urls = [line.strip() for line in f if line.strip()]
    
    results = {}
    for url in urls:
        try:
            screenshots = manager.take_screenshots(url)
            results[url] = screenshots
        except Exception as e:
            print(f"Error capturing screenshots for {url}: {str(e)}")
    
    # Save screenshot metadata
    with open('screenshot_metadata.json', 'w') as f:
        json.dump(results, f, indent=2)

if __name__ == "__main__":
    main() 