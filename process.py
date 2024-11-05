import pandas as pd
import requests
from urllib.parse import urlparse, urljoin
from concurrent.futures import ThreadPoolExecutor
import time

def load_excel_data(file_path):
    """
    Load data from Excel file and show available columns
    """
    try:
        df = pd.read_excel(file_path)
        print("\nAvailable columns in your Excel file:")
        for idx, column in enumerate(df.columns):
            print(f"{idx}: {column}")
        return df
    except Exception as e:
        print(f"Error loading Excel file: {e}")
        return None

def get_website_column(df):
    """
    Try to automatically identify the website column or ask for user input
    """
    website_columns = ['website', 'Website', 'web', 'Web', 'url', 'URL', 'link', 'Link']
    
    for col in website_columns:
        if col in df.columns:
            return col
    
    print("\nCouldn't automatically identify the website column.")
    print("Please enter the number of the column containing website URLs:")
    for idx, column in enumerate(df.columns):
        print(f"{idx}: {column}")
    
    while True:
        try:
            column_idx = int(input("Enter column number: "))
            if 0 <= column_idx < len(df.columns):
                return df.columns[column_idx]
            else:
                print("Invalid column number. Please try again.")
        except ValueError:
            print("Please enter a valid number.")

def is_social_platform(url):
    """
    Check if the URL is a social media or non-business platform
    """
    social_platforms = [
        'youtube.com', 'youtu.be',
        'facebook.com', 'fb.com',
        'instagram.com',
        'twitter.com', 'x.com',
        'linkedin.com',
        'tiktok.com',
        'pinterest.com',
        'snapchat.com',
        'reddit.com',
        'tumblr.com',
        'medium.com',
        'behance.net',
        'dribbble.com',
        'flickr.com',
        'vimeo.com',
        'soundcloud.com',
        'spotify.com',
        'wa.me',  # WhatsApp
        'telegram.org',
        'discord.com',
        'twitch.tv',
        'github.com',
        'gitlab.com',
        'bitbucket.org'
    ]
    
    parsed_url = urlparse(url.lower())
    domain = parsed_url.netloc.replace('www.', '')
    return any(platform in domain for platform in social_platforms)

def separate_by_website(df, website_column):
    """
    Separate data into two dataframes based on website presence and validity
    """
    try:
        # Create a mask for rows with non-empty website values
        has_website_mask = df[website_column].notna() & (df[website_column].astype(str) != '')
        
        # Initialize DataFrames
        has_website = pd.DataFrame()
        no_website = pd.DataFrame()
        
        # Process each row to check for social platforms
        for idx, row in df.iterrows():
            url = str(row[website_column]).strip() if has_website_mask[idx] else ''
            
            if url and not is_social_platform(normalize_url(url)):
                has_website = pd.concat([has_website, pd.DataFrame([row])], ignore_index=True)
            else:
                no_website = pd.concat([no_website, pd.DataFrame([row])], ignore_index=True)
        
        return has_website, no_website
    except Exception as e:
        print(f"Error separating data: {e}")
        return pd.DataFrame(), pd.DataFrame()

def normalize_url(url):
    """
    Normalize the URL by adding https:// if needed and removing trailing slashes
    """
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    return url.rstrip('/')

def check_response(url, timeout=10):
    """
    Check if a URL returns a valid response
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    try:
        response = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
        return response.status_code == 200, response.url
    except:
        return False, None

def is_same_domain(url1, url2):
    """
    Check if two URLs belong to the same domain
    """
    domain1 = urlparse(url1.lower()).netloc.replace('www.', '')
    domain2 = urlparse(url2.lower()).netloc.replace('www.', '')
    return domain1 == domain2

def is_ecommerce_site(base_url):
    """
    Check if a website is an e-commerce site by looking for checkout pages
    """
    try:
        base_url = normalize_url(base_url)
        original_domain = urlparse(base_url).netloc.replace('www.', '')
        
        # First check if it's a social platform
        if is_social_platform(base_url):
            print(f"Social platform detected: {base_url}")
            return False
        
        # Common checkout page patterns
        checkout_patterns = [
            '/checkout',
            '/cart',
            '/basket',
            '/shopping-cart',
            '/shop/checkout',
            '/checkout/cart',
            '/order',
            '/my-cart',
            '/viewcart',
            '/store/checkout',
            '/panier',  # French
            '/warenkorb',  # German
            '/carrello',  # Italian
            '/carro',  # Spanish
            '/winkelwagen'  # Dutch
        ]

        # First check the base URL
        base_valid, redirected_url = check_response(base_url)
        if not base_valid:
            print(f"Could not access base URL: {base_url}")
            return False

        # Verify we're still on the same domain after redirect
        if redirected_url and not is_same_domain(base_url, redirected_url):
            print(f"Redirected to different domain: {redirected_url}")
            return False

        # Use the redirected URL as the base if available and on same domain
        base_url = redirected_url or base_url

        # Check for common e-commerce platforms in the HTML
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        try:
            response = requests.get(base_url, headers=headers, timeout=10)
            content = response.text.lower()
            
            # Check for common e-commerce platforms
            ecommerce_platforms = [
                'shopify',
                'woocommerce',
                'magento',
                'prestashop',
                'opencart',
                'bigcommerce',
                'salesforce commerce',
                'wix stores',
                'square online store'
            ]
            
            if any(platform in content for platform in ecommerce_platforms):
                print(f"E-commerce platform detected for {base_url}")
                return True
        except:
            pass

        # Check each checkout pattern
        for pattern in checkout_patterns:
            checkout_url = urljoin(base_url, pattern)
            try:
                valid, redirected_checkout = check_response(checkout_url)
                if valid and is_same_domain(base_url, redirected_checkout):
                    print(f"Checkout page found at: {checkout_url}")
                    return True
            except Exception as e:
                continue

        return False
        
    except Exception as e:
        print(f"Error checking website {base_url}: {e}")
        return False

def process_websites(df_with_websites, website_column):
    """
    Process websites and separate them into e-commerce and non-e-commerce
    """
    ecommerce_sites = []
    normal_sites = []
    total = len(df_with_websites)
    
    print(f"\nProcessing {total} websites...")
    
    def process_row(row):
        url = row[website_column]
        if isinstance(url, str) and url.strip():
            print(f"\nChecking: {url}")
            if is_ecommerce_site(url):
                print(f"✓ E-commerce site found: {url}")
                ecommerce_sites.append(row)
            else:
                print(f"× Not an e-commerce site: {url}")
                normal_sites.append(row)
                
    # Process websites with progress tracking
    with ThreadPoolExecutor(max_workers=5) as executor:
        list(executor.map(process_row, df_with_websites.to_dict('records')))
        
    return pd.DataFrame(ecommerce_sites), pd.DataFrame(normal_sites)

def save_to_excel(no_website_df, normal_website_df, ecommerce_df, output_file):
    """
    Save the three dataframes to separate sheets in an Excel file
    """
    try:
        with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
            no_website_df.to_excel(writer, sheet_name='No Website', index=False)
            normal_website_df.to_excel(writer, sheet_name='Normal Website', index=False)
            ecommerce_df.to_excel(writer, sheet_name='E-commerce Website', index=False)
        print(f"\nData successfully saved to {output_file}")
    except Exception as e:
        print(f"Error saving Excel file: {e}")

def main():
    # Input and output file paths
    input_file = 'input_data.xlsx'  # Replace with your input file path
    output_file = 'processed_data.xlsx'  # Replace with your desired output file path
    
    # Load data
    print("Loading data...")
    df = load_excel_data(input_file)
    if df is None:
        return
    
    # Get the correct website column
    website_column = get_website_column(df)
    print(f"\nUsing column '{website_column}' for website URLs")
    
    # Separate based on website presence
    print("\nSeparating data based on website presence...")
    has_website_df, no_website_df = separate_by_website(df, website_column)
    
    # Process websites to identify e-commerce sites
    print(f"\nProcessing websites to identify e-commerce sites...")
    ecommerce_df, normal_website_df = process_websites(has_website_df, website_column)
    
    # Save results
    print("\nSaving results...")
    save_to_excel(no_website_df, normal_website_df, ecommerce_df, output_file)
    
    # Print summary
    print("\nProcessing Summary:")
    print(f"Total records: {len(df)}")
    print(f"No website: {len(no_website_df)}")
    print(f"Normal website: {len(normal_website_df)}")
    print(f"E-commerce website: {len(ecommerce_df)}")

if __name__ == "__main__":
    main()

