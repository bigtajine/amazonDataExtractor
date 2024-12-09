import os
import re
import pandas as pd
from bs4 import BeautifulSoup
import concurrent.futures
from tqdm import tqdm
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
import time
import random
import logging
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

# Author: bigtajine
# Filename: AmazonDataExtractor.py
# Last Modified: 2024-11-19

# Suppress logging
logging.getLogger('selenium.webdriver.remote.remote_connection').setLevel(logging.ERROR)

def save_html_content(driver, url, output_path):
    driver.get(url)
    time.sleep(random.uniform(10, 20))  # Introduce a random delay between 10 to 20 seconds
    with open(output_path, 'w', encoding='utf-8') as file:
        file.write(driver.page_source)

def extract_product_info(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')

    # Extract title
    title_tag = soup.find(id='productTitle')
    title = title_tag.get_text(strip=True) if title_tag else 'Title not found'

    # Extract bullet points
    bullet_points = [li.get_text(strip=True) for li in soup.select('#feature-bullets ul.a-unordered-list li')]

    # Extract product description
    description_tag = soup.find(id='productDescription')
    description = description_tag.get_text(strip=True) if description_tag else 'Description not found'

    return {
        'title': title,
        'bullet_points': bullet_points,
        'description': description
    }

def configure_chrome_options(language_code):
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument(f'--lang={language_code}')
    options.add_argument('--log-level=3')  # Suppress logs
    options.add_experimental_option('excludeSwitches', ['enable-logging'])
    return options

def process_single_file(args):
    driver, asin, country_code, html_folder = args
    url = f'https://www.amazon.{country_code}/dp/{asin}'
    html_path = os.path.join(html_folder, f'{asin}.html')
    
    # Save HTML content
    save_html_content(driver, url, html_path)
    
    # Read the saved HTML content
    with open(html_path, 'r', encoding='utf-8') as file:
        html_content = file.read()
    
    product_info = extract_product_info(html_content)

    return {
        'ASIN': asin,
        'Title': product_info['title'],
        'Description': product_info['description'],
        'Bullet Point 1': product_info['bullet_points'][0] if len(product_info['bullet_points']) > 0 else '',
        'Bullet Point 2': product_info['bullet_points'][1] if len(product_info['bullet_points']) > 1 else '',
        'Bullet Point 3': product_info['bullet_points'][2] if len(product_info['bullet_points']) > 2 else '',
        'Bullet Point 4': product_info['bullet_points'][3] if len(product_info['bullet_points']) > 3 else '',
        'Bullet Point 5': product_info['bullet_points'][4] if len(product_info['bullet_points']) > 4 else '',
        'URL': url
    }
def process_html_files(output_folder, asins_file, countries, progress_var):
    os.makedirs(output_folder, exist_ok=True)

    # Read ASINs from the input file
    with open(asins_file, 'r') as file:
        asins = [line.strip() for line in file.readlines()]

    total_tasks = len(countries) * len(asins)
    task_count = 0

    for country_code, language_code in countries:
        country_folder = os.path.join(output_folder, country_code)
        os.makedirs(country_folder, exist_ok=True)
        html_folder = os.path.join(country_folder, 'html_files')
        os.makedirs(html_folder, exist_ok=True)
        country_output_file = os.path.join(country_folder, f'products_info_{country_code}.xlsx')

        options = configure_chrome_options(language_code)
        drivers = [webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options) for _ in range(5)]
        
        # Prepare arguments for parallel processing
        args = [(drivers[i % len(drivers)], asins[i], country_code, html_folder) for i in range(len(asins))]
        
        data = []
        # Use ThreadPoolExecutor for parallel processing with fewer workers
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            for result in tqdm(executor.map(process_single_file, args), total=len(args), desc=f"Processing for {country_code}"):
                data.append(result)
                task_count += 1
                progress_var.set((task_count / total_tasks) * 100)
        
        # Close all drivers
        for driver in drivers:
            driver.quit()
        
        df = pd.DataFrame(data)

        # Create the output directory if it doesn't exist
        os.makedirs(os.path.dirname(country_output_file), exist_ok=True)

        df.to_excel(country_output_file, index=False)
        print(f'Processing complete for {country_code}. Output saved to', country_output_file)
# Tkinter GUI
class AmazonDataExtractorApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("AmazonDataExtractor")
        self.geometry("400x600")
        self.configure(bg="#E0FFFF")  # Pastel blue background

        self.countries = {
            "Amazon de": ("de", "de"),
            "Amazon co.uk": ("co.uk", "en"),
            "Amazon com.be": ("com.be", "fr"),
            "Amazon fr": ("fr", "fr"),
            "Amazon es": ("es", "es"),
            "Amazon se": ("se", "sv"),
            "Amazon nl": ("nl", "nl"),
            "Amazon it": ("it", "it"),
            "Amazon pl": ("pl", "pl")
        }

        self.create_widgets()

    def create_widgets(self):
        font_style = ("Arial", 12)

        self.lbl_asins = tk.Label(self, text="ASINs File:", font=font_style, bg="#E0FFFF")
        self.lbl_asins.pack(pady=5)

        self.entry_asins = tk.Entry(self, width=50, font=font_style)
        self.entry_asins.pack(pady=5)

        self.btn_browse_asins = tk.Button(self, text="Browse", command=self.browse_asins, font=font_style, bg="#B0E0E6")
        self.btn_browse_asins.pack(pady=5)

        self.lbl_output = tk.Label(self, text="Output Folder:", font=font_style, bg="#E0FFFF")
        self.lbl_output.pack(pady=5)

        self.entry_output = tk.Entry(self, width=50, font=font_style)
        self.entry_output.pack(pady=5)

        self.btn_browse_output = tk.Button(self, text="Browse", command=self.browse_output, font=font_style, bg="#B0E0E6")
        self.btn_browse_output.pack(pady=5)

        self.lbl_countries = tk.Label(self, text="Select Amazon Countries:", font=font_style, bg="#E0FFFF")
        self.lbl_countries.pack(pady=5)

        self.country_var = tk.StringVar(value=list(self.countries.keys()))

        self.country_menu = tk.Listbox(self, listvariable=self.country_var, selectmode='multiple', font=font_style, bg="#E0FFFF")
        self.country_menu.pack(pady=5, fill=tk.X, padx=20)

        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(self, variable=self.progress_var, maximum=100)
        self.progress_bar.pack(pady=20, fill=tk.X, padx=20)

        self.btn_start = tk.Button(self, text="Start", command=self.start_crawling, font=font_style, bg="#B0E0E6")
        self.btn_start.pack(pady=20)

    def browse_asins(self):
        file_path = filedialog.askopenfilename(filetypes=[("Text Files", "*.txt")])
        if file_path:
            self.entry_asins.delete(0, tk.END)
            self.entry_asins.insert(0, file_path)

    def browse_output(self):
        folder_path = filedialog.askdirectory()
        if folder_path:
            self.entry_output.delete(0, tk.END)
            self.entry_output.insert(0, folder_path)

    def start_crawling(self):
        asins_file = self.entry_asins.get()
        output_folder = self.entry_output.get()
        selected_indices = self.country_menu.curselection()
        selected_countries = [self.countries[self.country_menu.get(i)] for i in selected_indices]

        if not asins_file or not output_folder or not selected_countries:
            messagebox.showerror("Error", "Please provide all the required inputs.")
            return

        process_html_files(output_folder, asins_file, selected_countries, self.progress_var)
        messagebox.showinfo("Success", "Processing complete!")

if __name__ == "__main__":
    app = AmazonDataExtractorApp()
    app.mainloop()
