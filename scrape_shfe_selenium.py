import time
import csv
import json
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def scrape_shfe_data():
    # URL to scrape
    url = "https://www.shfe.com.cn/reports/marketdata/delayedquotes/?query_options=1&query_date=20260105&query_params=delaymarket_f&query_product_code=ag_f"
    
    # Setup Chrome options
    chrome_options = Options()
    # chrome_options.add_argument("--headless")  # Uncomment to run in headless mode
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    
    print("Launching browser...")
    driver = webdriver.Chrome(options=chrome_options)
    
    try:
        print(f"Navigating to {url}...")
        driver.get(url)
        
        # Wait for the table to load (waiting for a cell with text 'ag26' or just the table body)
        print("Waiting for page to load...")
        wait = WebDriverWait(driver, 10)
        wait.until(EC.presence_of_element_located((By.CLASS_NAME, "el-table__body-wrapper")))
        
        # Give it a moment for dynamic content to fully render
        time.sleep(3)
        
        print("Extracting data...")
        # This JavaScript is identical to what the browser subagent used
        extraction_script = """
        return (() => {
            let result = [];
            const headers = [];
            const headerElements = document.querySelectorAll('.el-table__header-wrapper th .cell');
            headerElements.forEach(header => headers.push(header.innerText.trim()));
            
            const rows = document.querySelectorAll('.el-table__body-wrapper .el-table__row');
            rows.forEach(row => {
                const cells = row.querySelectorAll('td .cell');
                const rowData = {};
                cells.forEach((cell, index) => {
                    if (headers[index]) {
                        rowData[headers[index]] = cell.innerText.trim();
                    }
                });
                // Filter for contracts starting with 'ag26'
                if (rowData[headers[0]] && rowData[headers[0]].startsWith('ag26')) {
                    result.push(rowData);
                }
            });
            return result;
        })();
        """
        
        data = driver.execute_script(extraction_script)
        
        if not data:
            print("No data found!")
            return

        print(f"Found {len(data)} rows.")
        
        # Save to JSON with the exact format requested
        json_file = 'shfe_market_data.json'
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"Saved data to {json_file}")
        
        
    except Exception as e:
        print(f"An error occurred: {e}")
        
    finally:
        print("Closing browser...")
        driver.quit()

if __name__ == "__main__":
    scrape_shfe_data()
