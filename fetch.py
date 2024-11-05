import pandas as pd
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from datetime import datetime
from urllib.parse import quote
from selenium.common.exceptions import StaleElementReferenceException, TimeoutException
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def clean_string(s):
    """Clean string by removing non-printable characters"""
    if not s:
        return ''
    return ''.join(filter(lambda x: x.isprintable(), str(s))).strip()

def get_user_input():
    """Get search parameters from user"""
    print("\nGoogle Maps Business Scraper")
    print("-" * 30)
    location = input("Enter location (e.g., 'New York, NY'): ").strip()
    niche = input("Enter business type/niche (e.g., 'restaurants'): ").strip()
    try:
        max_results = int(input("Enter maximum number of results to fetch (default 100): ").strip() or "100")
    except ValueError:
        max_results = 100
    return location, niche, max_results

class GoogleMapsScraper:
    def __init__(self):
        """Initialize the scraper with Chrome options"""
        chrome_options = webdriver.ChromeOptions()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--lang=en')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        self.driver = webdriver.Chrome(options=chrome_options)
        self.wait = WebDriverWait(self.driver, 15)

    def generate_search_url(self, query, location):
        """Generate Google Maps search URL"""
        search_query = quote(f"{query} in {location}")
        return f"https://www.google.com/maps/search/{search_query}"

    def wait_for_results(self):
        """Wait for search results to load and become visible"""
        try:
            time.sleep(5)  # Initial wait time
            self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div[role='feed']")))
            return True
        except TimeoutException:
            print("Timeout waiting for results to load.")
            return False

    def scroll_results(self, max_scrolls=10):
        """Scroll through results panel to load more places"""
        try:
            scrollable_div = self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.m6QErb")))
            last_height = 0
            for i in range(max_scrolls):
                self.driver.execute_script('arguments[0].scrollTop = arguments[0].scrollHeight', scrollable_div)
                time.sleep(3)
                new_height = self.driver.execute_script('return arguments[0].scrollHeight', scrollable_div)
                if new_height == last_height:
                    break
                last_height = new_height
        except Exception as e:
            print(f"Error during scrolling: {e}")

    def find_results(self):
        """Find all result elements"""
        return self.wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div.Nv2PK")))

    def extract_business_info(self, result):
        """Extract business information from the details panel"""
        try:
            result.click()
            time.sleep(3)

            # Initialize business info dictionary
            info = {}

            # Extract name
            try:
                name = ""
                # Extract name
                try:
                    result_element = self.driver.find_element(By.CSS_SELECTOR, "a.hfpxzc")
                    aria_label = result_element.get_attribute('aria-label')
                    if aria_label:
                        name = aria_label.split(' · ')[0].strip()
                except Exception as e:
                    print(f"Error getting name: {e}")
                
                # If name is not found, try other selectors
                if not name:
                    name_selectors = [
                        "h1.fontHeadlineLarge", "h1.DUwDvf", "div[role='heading'][aria-level='1']",
                        "div.fontHeadlineLarge", "div.qBF1Pd.fontHeadlineSmall"
                    ]
                    for selector in name_selectors:
                        try:
                            element = self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
                            name = element.text
                            if name:
                                break
                        except Exception as e:
                            print(f"Error extracting name with selector {selector}: {e}")
                info['name'] = clean_string(name)
            except Exception as e:
                print(f"Error getting name: {e}")
                info['name'] = ""

            # Extract website
            try:
                website = ""
                website_elements = self.driver.find_elements(
                    By.CSS_SELECTOR,
                    "a[data-item-id='authority'], a[data-tooltip='Open website'], a[href^='http']:not([href*='google'])"
                )
                for element in website_elements:
                    href = element.get_attribute('href')
                    if href and 'google' not in href:
                        website = href
                        break
                info['website'] = clean_string(website)
            except Exception as e:
                print(f"Error getting website: {e}")
                info['website'] = ""

            # Extract address
            try:
                address = ""
                address_elements = self.driver.find_elements(
                    By.CSS_SELECTOR,
                    "button[data-item-id*='address'], div[data-tooltip*='Copy address'], div.rogA2c"
                )
                for element in address_elements:
                    text = element.text
                    if text and len(text) > 5:
                        address = text
                        break
                info['address'] = clean_string(address)
            except Exception as e:
                print(f"Error getting address: {e}")
                info['address'] = ""

            # Extract phone
            try:
                phone = ""
                phone_elements = self.driver.find_elements(
                    By.CSS_SELECTOR,
                    "button[data-item-id*='phone:tel:'], div[data-tooltip*='Copy phone number'], span[aria-label*='phone']"
                )
                for element in phone_elements:
                    text = element.text or element.get_attribute('aria-label')
                    if text and any(char.isdigit() for char in text):
                        phone = text
                        break
                info['phone'] = clean_string(phone)
            except Exception as e:
                print(f"Error getting phone: {e}")
                info['phone'] = ""

            # Extract rating and reviews
            try:
                rating = ""
                reviews = ""
                rating_elements = self.driver.find_elements(
                    By.CSS_SELECTOR,
                    "span.ceNzKf, div.F7nice span"
                )
                for element in rating_elements:
                    text = element.text
                    if text and '(' in text:
                        parts = text.split('(')
                        rating = parts[0].strip()
                        reviews = ''.join(filter(str.isdigit, parts[1]))
                        break
                info['rating'] = clean_string(rating)
                info['reviews'] = clean_string(reviews)
            except Exception as e:
                print(f"Error getting rating/reviews: {e}")
                info['rating'] = ""
                info['reviews'] = ""

            return info

        except Exception as e:
            print(f"Error extracting business info: {e}")
            return None

    def scrape(self, location, niche, max_results):
        search_url = self.generate_search_url(niche, location)
        self.driver.get(search_url)
        
        if not self.wait_for_results():
            print("Failed to load results.")
            return []

        self.scroll_results()
        results = self.find_results()
        data = []
        
        for i, result in enumerate(results[:max_results]):
            for attempt in range(3):
                try:
                    info = self.extract_business_info(result)
                    if info and any(info.values()):
                        data.append(info)
                        print(f"Scraped {i + 1}/{max_results}: {info.get('name', 'N/A')}")
                        break
                    time.sleep(2)
                except StaleElementReferenceException:
                    print(f"Retrying extraction for result {i + 1}/{max_results}...")
                    results = self.find_results()
                    if i < len(results):
                        result = results[i]
                    time.sleep(2)
            else:
                print(f"Failed to extract info for {i + 1}/{max_results}")

        return data

    def close(self):
        """Close the webdriver"""
        self.driver.quit()

if __name__ == '__main__':
    try:
        location, niche, max_results = get_user_input()
        scraper = GoogleMapsScraper()
        data = scraper.scrape(location, niche, max_results)
        
        if data:
            df = pd.DataFrame(data)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'business_data.csv'
            df.to_csv(filename, index=False, encoding='utf-8')
            print(f"\nSuccessfully scraped {len(data)} businesses")
            print(f"Data saved to {filename}")
        else:
            print("\nNo data was scraped. Please check the search parameters and try again.")
    except Exception as e:
        logging.error(f"An unexpected error occurred: {str(e)}")
    finally:
        scraper.close()








