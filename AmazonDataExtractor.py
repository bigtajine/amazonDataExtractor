"""
Amazon Data Extractor - Extracts titles, bullet points, and descriptions via ASINs.
Author: bigtajine
Last Modified: 2025-04-08
"""

import os
import re
import queue
import threading
import logging
import time
import random
import pandas as pd
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

logging.getLogger("selenium.webdriver.remote.remote_connection").setLevel(logging.ERROR)

# Amazon ASINs are 10 characters (alphanumeric)
ASIN_PATTERN = re.compile(r"^[A-Z0-9]{10}$")


def is_valid_asin(asin: str) -> bool:
    """Return True if the string is a valid Amazon ASIN."""
    return bool(asin and ASIN_PATTERN.match(asin.strip()))


def extract_product_info(html_content: str) -> dict:
    """Extract title, bullet points, and description from product page HTML."""
    soup = BeautifulSoup(html_content, "html.parser")
    title_el = soup.find(id="productTitle")
    title = title_el.get_text(strip=True) if title_el else "Title not found"
    bullet_els = soup.select("#feature-bullets ul.a-unordered-list li")
    bullet_points = [li.get_text(strip=True) for li in bullet_els]
    desc_el = soup.find(id="productDescription")
    description = desc_el.get_text(strip=True) if desc_el else "Description not found"
    return {"title": title, "bullet_points": bullet_points, "description": description}


def process_single_asin(
    asin: str, country_code: str, html_folder: str, language_code: str
) -> dict | None:
    """
    Fetch one product page and extract data. Uses its own driver (thread-safe).
    Returns a row dict or None on failure.
    """
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument(f"--lang={language_code}")
    options.add_argument("--log-level=3")
    options.add_experimental_option("excludeSwitches", ["enable-logging"])

    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()), options=options
    )
    try:
        url = f"https://www.amazon.{country_code}/dp/{asin}"
        driver.get(url)
        time.sleep(random.uniform(2, 5))
        html_content = driver.page_source
        html_path = os.path.join(html_folder, f"{asin}.html")
        os.makedirs(os.path.dirname(html_path) or ".", exist_ok=True)
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        product = extract_product_info(html_content)
        bullets = product["bullet_points"]
        return {
            "ASIN": asin,
            "Title": product["title"],
            "Description": product["description"],
            "Bullet Point 1": bullets[0] if len(bullets) > 0 else "",
            "Bullet Point 2": bullets[1] if len(bullets) > 1 else "",
            "Bullet Point 3": bullets[2] if len(bullets) > 2 else "",
            "Bullet Point 4": bullets[3] if len(bullets) > 3 else "",
            "Bullet Point 5": bullets[4] if len(bullets) > 4 else "",
            "URL": url,
        }
    except Exception as e:
        print(f"Error processing {asin} ({country_code}): {e}")
        return None
    finally:
        driver.quit()


def process_country(
    country_code: str,
    language_code: str,
    asins: list[str],
    output_folder: str,
    ui_queue: queue.Queue,
    total_tasks: int,
    task_offset: int,
) -> None:
    """Process all ASINs for one country and write Excel + HTML files."""
    country_folder = os.path.join(output_folder, country_code)
    html_folder = os.path.join(country_folder, "html_files")
    os.makedirs(html_folder, exist_ok=True)
    completed = 0
    data = []
    with ThreadPoolExecutor(max_workers=3) as executor:
        future_to_asin = {
            executor.submit(
                process_single_asin, asin, country_code, html_folder, language_code
            ): asin
            for asin in asins
        }
        for future in as_completed(future_to_asin):
            result = future.result()
            if result:
                data.append(result)
            completed += 1
            ui_queue.put(
                {
                    "progress": ((task_offset + completed) / total_tasks) * 100,
                    "status": f"{country_code}: {completed}/{len(asins)}",
                }
            )
    out_file = os.path.join(country_folder, f"products_info_{country_code}.xlsx")
    os.makedirs(country_folder, exist_ok=True)
    if data:
        pd.DataFrame(data).to_excel(out_file, index=False)
    print(f"Saved {out_file} ({len(data)} rows).")


def run_extraction(
    asins_file: str,
    output_folder: str,
    selected_countries: list[tuple],
    progress_bar: ttk.Progressbar,
    status_label: tk.Label,
    run_button: tk.Button,
    root: tk.Tk,
) -> None:
    """Run extraction in a background thread; update UI via queue."""
    ui_queue = queue.Queue()

    def update_ui():
        try:
            while True:
                msg = ui_queue.get_nowait()
                if msg is None:
                    progress_bar["value"] = 100
                    status_label.config(text="Done.")
                    run_button.config(state=tk.NORMAL)
                    return
                if msg.get("enable_button"):
                    run_button.config(state=tk.NORMAL)
                    status_label.config(text=msg.get("status", "Error."))
                    if msg.get("show_error"):
                        messagebox.showerror("Error", msg["show_error"])
                    return
                progress_bar["value"] = msg["progress"]
                status_label.config(text=msg["status"])
        except queue.Empty:
            pass
        root.after(100, update_ui)

    def worker():
        try:
            with open(asins_file, "r", encoding="utf-8", errors="replace") as f:
                lines = [
                    line.strip()
                    for line in f
                    if line.strip() and not line.strip().startswith("#")
                ]
            asins = [a for a in lines if is_valid_asin(a)]
            if not asins:
                ui_queue.put(
                    {"enable_button": True, "status": "No valid ASINs.", "show_error": "No valid ASINs in file."}
                )
                return
            total_tasks = len(selected_countries) * len(asins)
            task_offset = 0
            for country_code, language_code in selected_countries:
                process_country(
                    country_code,
                    language_code,
                    asins,
                    output_folder,
                    ui_queue,
                    total_tasks,
                    task_offset,
                )
                task_offset += len(asins)
            ui_queue.put(None)
        except FileNotFoundError:
            ui_queue.put(
                {
                    "enable_button": True,
                    "status": "File not found.",
                    "show_error": f"File not found: {asins_file}",
                }
            )
        except Exception as e:
            ui_queue.put(
                {"enable_button": True, "status": "Error.", "show_error": str(e)}
            )

    threading.Thread(target=worker, daemon=True).start()
    root.after(100, update_ui)


# --- GUI ---
COUNTRY_OPTIONS = {
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
    "Amazon.tr": ("tr", "tr"),
}


class AmazonDataExtractorApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("amazonDataExtractor")
        self.resizable(True, True)
        self.minsize(400, 420)
        self.create_widgets()

    def select_file(self):
        path = filedialog.askopenfilename(
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        if path:
            self.file_label.config(text=path)

    def select_directory(self):
        path = filedialog.askdirectory()
        if path:
            self.directory_label.config(text=path)

    def create_widgets(self):
        font_style = ("Cascadia Mono", 10)
        if "Cascadia Mono" not in tk.font.families():
            font_style = ("TkDefaultFont", 10)

        tk.Label(self, text="amazonDataExtractor", font=("Cascadia Mono", 16, "bold")).grid(
            row=0, column=0, sticky="w", padx=10, pady=(10, 5)
        )
        tk.Label(self, text="Marketplace", font=font_style).grid(
            row=1, column=0, sticky="w", padx=10, pady=(10, 0)
        )
        self.country_listbox = tk.Listbox(
            self, selectmode="multiple", font=font_style, height=6
        )
        for name in COUNTRY_OPTIONS:
            self.country_listbox.insert(tk.END, name)
        self.country_listbox.grid(row=2, column=0, sticky="ew", padx=10, pady=2)
        tk.Label(self, text="(Hold Ctrl/Cmd to select multiple)", font=("TkDefaultFont", 8), fg="gray").grid(
            row=3, column=0, sticky="w", padx=10
        )

        tk.Label(self, text="ASINs (one per line, .txt)", font=font_style).grid(
            row=4, column=0, sticky="w", padx=10, pady=(10, 0)
        )
        self.file_label = tk.Label(self, text="No file selected", font=font_style, anchor="w")
        self.file_label.grid(row=5, column=0, sticky="ew", padx=10)
        tk.Button(self, text="Select File", command=self.select_file, font=font_style).grid(
            row=6, column=0, sticky="w", padx=10, pady=2
        )

        tk.Label(self, text="Save Directory", font=font_style).grid(
            row=7, column=0, sticky="w", padx=10, pady=(10, 0)
        )
        self.directory_label = tk.Label(
            self, text="No directory selected", font=font_style, anchor="w"
        )
        self.directory_label.grid(row=8, column=0, sticky="ew", padx=10)
        tk.Button(self, text="Select Directory", command=self.select_directory, font=font_style).grid(
            row=9, column=0, sticky="w", padx=10, pady=2
        )

        self.run_button = tk.Button(self, text="Run", font=font_style, command=self.start_crawling)
        self.run_button.grid(row=10, column=0, pady=15)

        self.progress_bar = ttk.Progressbar(self, orient=tk.HORIZONTAL, mode="determinate")
        self.progress_bar.grid(row=11, column=0, sticky="ew", padx=10, pady=2)
        self.status_label = tk.Label(self, text="", font=font_style, anchor="w")
        self.status_label.grid(row=12, column=0, sticky="ew", padx=10, pady=(0, 10))

        self.grid_columnconfigure(0, weight=1)

    def start_crawling(self):
        asins_file = self.file_label.cget("text")
        output_folder = self.directory_label.cget("text")
        selected_indices = self.country_listbox.curselection()
        selected_countries = [
            COUNTRY_OPTIONS[self.country_listbox.get(i)] for i in selected_indices
        ]

        if not asins_file or asins_file == "No file selected":
            messagebox.showerror("Error", "Please select an ASIN list file.")
            return
        if not output_folder or output_folder == "No directory selected":
            messagebox.showerror("Error", "Please select a save directory.")
            return
        if not selected_countries:
            messagebox.showerror("Error", "Please select at least one marketplace.")
            return

        self.run_button.config(state=tk.DISABLED)
        self.status_label.config(text="Starting...")
        self.progress_bar["value"] = 0
        run_extraction(
            asins_file,
            output_folder,
            selected_countries,
            self.progress_bar,
            self.status_label,
            self.run_button,
            self,
        )


if __name__ == "__main__":
    app = AmazonDataExtractorApp()
    app.mainloop()
