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
import threading

# Suppress logging
logging.getLogger('selenium.webdriver.remote.remote_connection').setLevel(logging.ERROR)

# Utility Functions
def save_html_content(driver, url, output_path):
    driver.get(url)
    time.sleep(random.uniform(10, 20))  # Random delay
    with open(output_path, 'w', encoding='utf-8') as file:
        file.write(driver.page_source)

def extract_product_info(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    title = soup.find(id='productTitle').get_text(strip=True) if soup.find(id='productTitle') else 'Title not found'
    bullet_points = [li.get_text(strip=True) for li in soup.select('#feature-bullets ul.a-unordered-list li')]
    description = soup.find(id='productDescription').get_text(strip=True) if soup.find(id='productDescription') else 'Description not found'
    return {'title': title, 'bullet_points': bullet_points, 'description': description}

def configure_chrome_options(language_code):
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument(f'--lang={language_code}')
    options.add_argument('--log-level=3')
    options.add_experimental_option('excludeSwitches', ['enable-logging'])
    return options

def process_single_file(args):
    driver, asin, country_code, html_folder = args
    url = f'https://www.amazon.{country_code}/dp/{asin}'
    html_path = os.path.join(html_folder, f'{asin}.html')
    
    # Save HTML content and read it
    save_html_content(driver, url, html_path)
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
        os.makedirs(os.path.dirname(country_output_file), exist_ok=True)
        df.to_excel(country_output_file, index=False)
        print(f'Processing complete for {country_code}. Output saved to', country_output_file)

# Tkinter GUI
class AmazonDataExtractorApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("amazonDataExtractor")
        self.countries = {
            "Amazon.com": ("com", "en"),
            "Amazon.ca": ("ca", "en"),
            "Amazon.co.uk": ("co.uk", "en"),
            "Amazon.de": ("de", "de"),
            "Amazon.fr": ("fr", "fr"),
            "Amazon.it": ("it", "it"),
            "Amazon.es": ("es", "es"),
            "Amazon.com.mx": ("com.mx", "es"),
            "Amazon.in": ("in", "hi"),
            "Amazon.com.br": ("com.br", "pt"),
            "Amazon.au": ("au", "en"),
            "Amazon.nl": ("nl", "nl"),
            "Amazon.sg": ("sg", "en"),
            "Amazon.se": ("se", "sv"),
            "Amazon.pl": ("pl", "pl"),
            "Amazon.sa": ("sa", "ar"),
            "Amazon.ae": ("ae", "ar"),
            "Amazon.co.il": ("co.il", "he"),
            "Amazon.tr": ("tr", "tr")
        }
        self.create_widgets()
        self.resizable(False, False)
    
    def select_file(self):
        file_path = filedialog.askopenfilename(filetypes=[("Text files", "*.txt")])
        if file_path:
            self.file_label.config(text=file_path)

    def select_directory(self):
        folder_path = filedialog.askdirectory()
        if folder_path:
            self.directory_label.config(text=folder_path)

    def create_widgets(self):
        font_style = ("Cascadia Mono", 10)
        self.lbl_title = tk.Label(self, text="amazonDataExtractor", font=("Cascadia Mono", 16, 'bold'))
        self.lbl_title.grid(row=0, column=0, sticky="w")

        self.lbl_countries = tk.Label(self, text="Marketplace", font=font_style)
        self.lbl_countries.grid(row=1, column=0, sticky="w")

        self.country_var = tk.StringVar(value=list(self.countries.keys()))
        self.country_menu = tk.Listbox(self, listvariable=self.country_var, selectmode='multiple', font=font_style)
        self.country_menu.grid(row=2, column=0, sticky="ew")

        self.lbl_asins = tk.Label(self, text="ASINs", font=font_style)
        self.lbl_asins.grid(row=3, column=0, sticky="w")

        self.file_label = tk.Label(self, text="No file selected", font=font_style)
        self.file_label.grid(row=4, column=0, sticky="ew")

        self.btn_browse_asins = tk.Button(self, text="Select File", command=self.select_file, font=font_style)
        self.btn_browse_asins.grid(row=5, column=0, sticky="ew")

        self.lbl_output = tk.Label(self, text="Save Directory", font=font_style)
        self.lbl_output.grid(row=6, column=0, sticky="w")

        self.directory_label = tk.Label(self, text="No directory selected", font=font_style)
        self.directory_label.grid(row=7, column=0, sticky="ew")

        self.btn_browse_output = tk.Button(self, text="Select Directory", command=self.select_directory, font=font_style)
        self.btn_browse_output.grid(row=8, column=0, sticky="ew")

        self.btn_start = tk.Button(self, text="Run", command=self.start_crawling, font=font_style)
        self.btn_start.grid(row=9, column=0)

        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(self, variable=self.progress_var, maximum=100)
        self.progress_bar.grid(row=10, column=0, sticky="ew")

        self.grid_rowconfigure(0, weight=1) 
        self.grid_rowconfigure(2, weight=1) 
        self.grid_rowconfigure(4, weight=1) 
        self.grid_rowconfigure(6, weight=1) 
        self.grid_rowconfigure(9, weight=1) 
        self.grid_columnconfigure(0, weight=1)

    def start_crawling(self):
        asins_file = self.file_label.cget("text")
        output_folder = self.directory_label.cget("text")
        selected_indices = self.country_menu.curselection()
        selected_countries = [self.countries[self.country_menu.get(i)] for i in selected_indices]

        if not asins_file or not output_folder or not selected_countries:
            return

        threading.Thread(target=process_html_files, args=(output_folder, asins_file, selected_countries, self.progress_var)).start()

if __name__ == "__main__":
    app = AmazonDataExtractorApp()
    app.mainloop()
