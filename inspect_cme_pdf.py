import requests
import pdfplumber
import io

# Fetch and inspect the actual PDF structure
url = "https://www.cmegroup.com/delivery_reports/MetalsIssuesAndStopsReport.pdf"

headers = {
    'User-Agent': 'Mozilla/5.0'
}

print("Fetching PDF...")
response = requests.get(url, headers=headers, timeout=15)

if response.status_code == 200:
    pdf_bytes = io.BytesIO(response.content)
    
    with pdfplumber.open(pdf_bytes) as pdf:
        print(f"\nTotal pages: {len(pdf.pages)}\n")
        
        for page_num, page in enumerate(pdf.pages[:2]):  # Check first 2 pages
            print(f"=" * 60)
            print(f"PAGE {page_num + 1}")
            print("=" * 60)
            
            # Extract raw text
            text = page.extract_text()
            print("\nRAW TEXT (first 1000 chars):")
            print(text[:1000])
            
            # Extract tables
            tables = page.extract_tables()
            print(f"\nNumber of tables found: {len(tables)}")
            
            for table_num, table in enumerate(tables):
                print(f"\n--- Table {table_num + 1} ---")
                print(f"Rows: {len(table)}")
                if table:
                    print("First 5 rows:")
                    for row in table[:5]:
                        print(row)
else:
    print(f"Failed to fetch: {response.status_code}")
