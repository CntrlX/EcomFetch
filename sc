import pandas as pd
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from datetime import datetime
from urllib.parse import quote

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
            time.sleep(5)  # Increased initial wait time
            selectors = ["div[role='feed']", "div.m6QErb.DxyBCb.kA9KIf.dS8AEf", "div.m6QErb"]
            for selector in selectors:
                try:
                    self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
                    return True
                except:
                    continue
            return False
        except Exception as e:
            print(f"Error waiting for results: {e}")
            return False

    def scroll_results(self, max_scrolls=10):
        """Scroll through results panel to load more places"""
        try:
            scrollable_div = self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.m6QErb"))
            )
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
        """Find all result elements using multiple possible selectors"""
        result_selectors = ["a.hfpxzc", "div.Nv2PK", "div[role='article']"]
        for selector in result_selectors:
            try:
                results = self.wait.until(
                    EC.presence_of_all_elements_located((By.CSS_SELECTOR, selector))
                )
                if results:
                    return results
            except:
                continue
        return []

    def extract_business_info(self):
        """Extract business information from the details panel"""
        try:
            time.sleep(3)
            name = ""
            try:
                result_element = self.driver.find_element(By.CSS_SELECTOR, "a.hfpxzc")
                aria_label = result_element.get_attribute('aria-label')
                if aria_label:
                    name = aria_label.split(' · ')[0].strip()
            except:
                pass
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
                    except:
                        continue
            website, address, phone, rating, reviews = "", "", "", "", ""
            try:
                website_elements = self.driver.find_elements(
                    By.CSS_SELECTOR, "a[data-item-id='authority'], a[data-tooltip='Open website'], a[href^='http']:not([href*='google'])"
                )
                for element in website_elements:
                    href = element.get_attribute('href')
                    if href and 'google' not in href:
                        website = href
                        break
            except:
                pass
            try:
                address_elements = self.driver.find_elements(
                    By.CSS_SELECTOR, "button[data-item-id*='address'], div[data-tooltip*='Copy address'], div.rogA2c"
                )
                for element in address_elements:
                    text = element.text
                    if text and len(text) > 5:
                        address = text
                        break
            except:
                pass
            try:
                phone_elements = self.driver.find_elements(
                    By.CSS_SELECTOR, "button[data-item-id*='phone:tel:'], div[data-tooltip*='Copy phone number'], span[aria-label*='phone']"
                )
                for element in phone_elements:
                    text = element.text or element.get_attribute('aria-label')
                    if text and any(char.isdigit() for char in text):
                        phone = text
                        break
            except:
                pass
            try:
                rating_elements = self.driver.find_elements(By.CSS_SELECTOR, "span.ceNzKf, div.F7nice span")
                for element in rating_elements:
                    text = element.text
                    if text and '(' in text:
                        parts = text.split('(')
                        rating = parts[0].strip()
                        reviews = ''.join(filter(str.isdigit, parts[1]))
                        break
            except:
                pass
            business_info = {
                'name': name,
                'website': website,
                'address': address,
                'phone': phone,
                'rating': rating,
                'reviews': reviews
            }
            return business_info
        except Exception as e:
            print(f"Error extracting business info: {e}")
            return None

    def scrape_places(self, query, location, max_results=100):
        """Scrape business information from Google Maps"""
        businesses = []
        try:
            search_url = self.generate_search_url(query, location)
            self.driver.get(search_url)
            if not self.wait_for_results():
                return businesses
            self.scroll_results(max_scrolls=max_results//5)
            results = self.find_results()
            for i, result in enumerate(results[:max_results]):
                try:
                    aria_label = result.get_attribute('aria-label')
                    if aria_label:
                        print(f"Found business: {aria_label.split(' · ')[0]}")
                    try:
                        self.driver.execute_script("arguments[0].click();", result)
                    except:
                        result.click()
                    time.sleep(3)
                    business_info = self.extract_business_info()
                    if business_info:
                        businesses.append(business_info)
                except Exception as e:
                    print(f"Error processing result {i+1}: {e}")
                    continue
            return businesses
        except Exception as e:
            print(f"Error during scraping: {e}")
            return businesses

    def save_to_excel(self, businesses, filename):
        """Save scraped data to Excel file"""
        if businesses:
            df = pd.DataFrame(businesses)
            df.to_excel(filename, index=False)
            print(f"Data saved to {filename}")
        else:
            print("No data to save")

    def close(self):
        """Close the browser"""
        self.driver.quit()

def main():
    location, niche, max_results = get_user_input()
    scraper = GoogleMapsScraper()
    try:
        businesses = scraper.scrape_places(niche, location, max_results)
        if not businesses:
            print("No businesses found. Exiting...")
            return
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"scraped_data_{timestamp}.xlsx"
        scraper.save_to_excel(businesses, filename)
        print(f"\nScraping Summary: Total records scraped: {len(businesses)}")
    finally:
        scraper.close()

if __name__ == "__main__":
    main()
