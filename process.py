import pandas as pd
import requests
from urllib.parse import urlparse, urljoin
from concurrent.futures import ThreadPoolExecutor
import time
from flask import Flask, render_template, request, send_file, Response
import os
from werkzeug.utils import secure_filename
import queue
import threading

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
app.config['log_queue'] = queue.Queue()
app.config['processing_complete'] = threading.Event()

# Create uploads folder if it doesn't exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

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
    
    log_message(f"Processing {total} websites...")
    
    def process_row(row):
        url = row[website_column]
        if isinstance(url, str) and url.strip():
            log_message(f"Checking: {url}")
            if is_ecommerce_site(url):
                log_message(f"✓ E-commerce site found: {url}")
                ecommerce_sites.append(row)
            else:
                log_message(f"× Not an e-commerce site: {url}")
                normal_sites.append(row)
    
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

def log_message(message):
    """Add message to the log queue"""
    app.config['log_queue'].put(message)

@app.route('/', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        if 'file' not in request.files:
            return 'No file uploaded', 400
        
        file = request.files['file']
        if file.filename == '':
            return 'No file selected', 400
        
        if file and file.filename.endswith('.xlsx'):
            filename = secure_filename(file.filename)
            input_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            
            # Save uploaded file
            file.save(input_path)
            
            # Process the file
            df = load_excel_data(input_path)
            if df is None:
                return 'Error loading Excel file', 400
            
            # Try to automatically identify website column
            website_columns = ['website', 'Website', 'web', 'Web', 'url', 'URL', 'link', 'Link']
            website_column = None
            for col in website_columns:
                if col in df.columns:
                    website_column = col
                    break
            
            if website_column is None:
                # If column not found, show column selection page
                return render_template('select_column.html', 
                                    columns=list(df.columns),
                                    filename=filename)
            
            return process_excel_file(input_path, website_column)
            
        return 'Invalid file type. Please upload an Excel file.', 400
    
    return render_template('upload.html')

@app.route('/process', methods=['POST'])
def process_with_column():
    website_column = request.form.get('website_column')
    filename = request.form.get('filename')
    
    if not website_column or not filename:
        return 'Missing required parameters', 400
    
    # Reset processing state
    app.config['processing_complete'].clear()
    while not app.config['log_queue'].empty():
        app.config['log_queue'].get()
    
    return render_template('processing.html', 
                         filename=filename,
                         website_column=website_column)

@app.route('/start_processing', methods=['POST'])
def start_processing():
    filename = request.form.get('filename')
    website_column = request.form.get('website_column')
    
    if not filename or not website_column:
        return 'Missing parameters', 400
    
    input_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    output_path = os.path.join(app.config['UPLOAD_FOLDER'], f'processed_{filename}')
    
    try:
        df = load_excel_data(input_path)
        if df is None:
            return 'Error loading Excel file', 400
        
        # Process the data
        has_website_df, no_website_df = separate_by_website(df, website_column)
        ecommerce_df, normal_website_df = process_websites(has_website_df, website_column)
        
        # Save results
        save_to_excel(no_website_df, normal_website_df, ecommerce_df, output_path)
        
        app.config['processing_complete'].set()
        
        return send_file(
            output_path,
            as_attachment=True,
            download_name=f'processed_{filename}'
        )
    
    except Exception as e:
        log_message(f"Error: {str(e)}")
        app.config['processing_complete'].set()
        return 'Processing error', 500

@app.route('/stream_logs')
def stream_logs():
    def generate():
        while not app.config['processing_complete'].is_set() or not app.config['log_queue'].empty():
            try:
                message = app.config['log_queue'].get(timeout=1)
                yield f"data: {message}\n\n"
            except queue.Empty:
                continue
        yield "data: PROCESSING_COMPLETE\n\n"
    
    return Response(generate(), mimetype='text/event-stream')

def process_excel_file(input_path, website_column):
    """Helper function to process the Excel file with the selected column"""
    output_path = os.path.join(app.config['UPLOAD_FOLDER'], f'processed_{os.path.basename(input_path)}')
    
    df = load_excel_data(input_path)
    if df is None:
        return 'Error loading Excel file', 400
    
    # Process the data
    has_website_df, no_website_df = separate_by_website(df, website_column)
    ecommerce_df, normal_website_df = process_websites(has_website_df, website_column)
    
    # Save results
    save_to_excel(no_website_df, normal_website_df, ecommerce_df, output_path)
    
    # Return the processed file
    return send_file(
        output_path,
        as_attachment=True,
        download_name=f'processed_{os.path.basename(input_path)}'
    )

if __name__ == "__main__":
    app.run(debug=True)

