# amazonDataExtractor

Extracts Amazon product titles, bullet points, and descriptions via ASINs. Saves data as Excel (`.xlsx`) and stores a copy of each product page HTML per marketplace.

## Requirements

- **Python 3.10+**
- **Chrome** (installed on your system). ChromeDriver is installed automatically via `webdriver-manager`.

## Install

```bash
git clone https://github.com/bigtajine/amazonDataExtractor.git
cd amazonDataExtractor
pip install -r requirements.txt
```

## Usage

1. Run the app:
   ```bash
   python AmazonDataExtractor.py
   ```
2. **Marketplace** – Select one or more Amazon sites (e.g. Amazon.com, Amazon.co.uk). Use Ctrl/Cmd to select multiple.
3. **ASINs** – Click "Select File" and choose a `.txt` file with one ASIN per line. Lines starting with `#` and empty lines are ignored. Invalid ASINs (not 10 alphanumeric characters) are skipped.
4. **Save Directory** – Choose the folder where Excel files and HTML will be saved.
5. Click **Run**. Progress and status are shown; the Run button is disabled until the job finishes.

## ASIN file format

```text
B08N5WRWNW
B09V3KXJPB
# comment lines are ignored
B07XJ8C8F5
```

## Output

For each selected marketplace, the tool creates:

- **`{Save Directory}/{country}/products_info_{country}.xlsx`** – Columns: ASIN, Title, Description, Bullet Point 1–5, URL.
- **`{Save Directory}/{country}/html_files/{ASIN}.html`** – Raw product page HTML for that country.

Example:

- `C:\Output\com\products_info_com.xlsx`
- `C:\Output\com\html_files\B08N5WRWNW.html`
- `C:\Output\co.uk\products_info_co.uk.xlsx`

## Notes

- The tool uses headless Chrome and short random delays to reduce the chance of rate limits. Heavy use may still be throttled by Amazon.
- Each worker thread uses its own browser instance (thread-safe; no shared drivers).
