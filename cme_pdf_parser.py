import requests
import pdfplumber
import re
from datetime import datetime
import io


class CMEDeliveryParser:
    """
    Parse CME Metals Issues and Stops reports (PDF) for silver delivery data.
    PDFs use plain text format, not tables.
    """

    def __init__(self):
        self.headers = {"User-Agent": "Mozilla/5.0"}

    def fetch_pdf(self, url, timeout=15):
        """Fetch PDF from URL and return bytes"""
        try:
            response = requests.get(url, headers=self.headers, timeout=timeout)
            if response.status_code == 200:
                return io.BytesIO(response.content)
            return None
        except Exception as e:
            print(f"Error fetching PDF: {e}")
            return None

    def parse_daily_issues_stops(self):
        """
        Parse daily CME Metals Issues and Stops Report for silver.
        Returns: dict with issued and stopped contract counts
        """
        url = "https://www.cmegroup.com/delivery_reports/MetalsIssuesAndStopsReport.pdf"
        pdf_bytes = self.fetch_pdf(url)

        if not pdf_bytes:
            return {"error": "Failed to fetch PDF"}

        try:
            with pdfplumber.open(pdf_bytes) as pdf:
                silver_data = {
                    "issued": 0,
                    "stopped": 0,
                    "date": None,
                    "found": False,
                    "source": "CME Daily PDF",
                }

                # Extract all text from all pages
                full_text = ""
                for page in pdf.pages:
                    full_text += page.extract_text() + "\n"

                # Find date
                date_match = re.search(
                    r"BUSINESS DATE:\s*(\d{1,2}/\d{1,2}/\d{4})", full_text
                )
                if date_match:
                    silver_data["date"] = date_match.group(1)

                # Find silver contract sections
                # Look for patterns like "SILVER FUTURES" or "COMEX 5000 SILVER"
                silver_sections = re.finditer(
                    r"(SILVER FUTURES|COMEX 5000 SILVER|5000 SILVER).*?"
                    r"TOTAL:\s*(\d+)\s+(\d+)",
                    full_text,
                    re.DOTALL | re.IGNORECASE,
                )

                for match in silver_sections:
                    issued = int(match.group(2))
                    stopped = int(match.group(3))

                    # Sum up all silver contracts (might be multiple months)
                    silver_data["issued"] += issued
                    silver_data["stopped"] += stopped
                    silver_data["found"] = True

                if not silver_data["found"]:
                    return {
                        "error": "No silver delivery data found in PDF",
                        "date": silver_data.get("date"),
                        "note": "Market may be closed or no deliveries",
                    }

                return silver_data

        except Exception as e:
            return {"error": f"PDF parsing error: {str(e)}"}

    def parse_mtd_deliveries(self):
        """
        Parse CME Month-to-Date Metals Issues and Stops Report.
        Returns: dict with MTD cumulative totals
        """
        url = "https://www.cmegroup.com/delivery_reports/MetalsIssuesAndStopsMTDReport.pdf"
        pdf_bytes = self.fetch_pdf(url)

        if not pdf_bytes:
            return {"error": "Failed to fetch MTD PDF"}

        try:
            with pdfplumber.open(pdf_bytes) as pdf:
                mtd_data = {
                    "mtd_issued": 0,
                    "mtd_stopped": 0,
                    "month": None,
                    "found": False,
                    "source": "CME MTD PDF",
                }

                silver_section = None
                
                # Search all pages for SILVER section
                for page in pdf.pages:
                    text = page.extract_text()
                    
                    # Find all start indices of "CONTRACT:"
                    contract_starts = [m.start() for m in re.finditer(r"CONTRACT:", text)]
                    
                    for start in contract_starts:
                        # Extract the contract line to verify if it's SILVER
                        contract_line_end = text.find("\n", start)
                        if contract_line_end == -1:
                            contract_line = text[start:]
                        else:
                            contract_line = text[start:contract_line_end]
                        
                        # Check if this is the Silver contract
                        if "SILVER FUTURES" in contract_line:
                            # Try to extract month from contract line (e.g., "FEBRUARY 2026")
                            month_match = re.search(r"(JANUARY|FEBRUARY|MARCH|APRIL|MAY|JUNE|JULY|AUGUST|SEPTEMBER|OCTOBER|NOVEMBER|DECEMBER)\s+\d{4}", contract_line, re.IGNORECASE)
                            if month_match:
                                mtd_data["month"] = month_match.group(0).title()

                            # Found it. Now define the end of the section.
                            next_exchange = text.find("EXCHANGE:", contract_line_end)
                            
                            if next_exchange != -1:
                                end = next_exchange
                            else:
                                end = len(text)
                            
                            silver_section = text[start:end]
                            break
                    
                    if silver_section:
                        break

                if not silver_section:
                    return {
                        "error": "No MTD silver data found",
                        "month": mtd_data.get("month"),
                        "note": "Market may be closed or start of new month",
                    }

                # Extract date patterns: MM/DD/YYYY DAILY CUMULATIVE
                # Match lines with date followed by two numbers
                matches = re.findall(
                    r"(\d{1,2}/\d{1,2}/\d{4})\s+([0-9,]+)\s+([0-9,]+)", 
                    silver_section
                )

                if matches:
                    # The last entry contains the MTD cumulative total
                    last_entry = matches[-1]
                    cumulative = int(last_entry[2].replace(",", ""))
                    
                    mtd_data["mtd_issued"] = cumulative
                    mtd_data["mtd_stopped"] = cumulative
                    mtd_data["found"] = True
                
                return mtd_data

        except Exception as e:
            return {"error": f"MTD PDF parsing error: {str(e)}"}

    def parse_last_3_days_silver(self):
        """
        Parse last 3 days of COMEX 5000 SILVER FUTURES data from MTD PDF.
        Returns: list of dicts with INTENT DATE, DAILY, TOTAL CUMULATIVE
        """
        url = "https://www.cmegroup.com/delivery_reports/MetalsIssuesAndStopsMTDReport.pdf"
        pdf_bytes = self.fetch_pdf(url)

        if not pdf_bytes:
            return {"error": "Failed to fetch MTD PDF"}

        try:
            with pdfplumber.open(pdf_bytes) as pdf:
                # Search all pages for SILVER section
                silver_section = None
                for page in pdf.pages:
                    text = page.extract_text()
                    
                    # Find all start indices of "CONTRACT:"
                    contract_starts = [m.start() for m in re.finditer(r"CONTRACT:", text)]
                    
                    for start in contract_starts:
                        # Extract the contract line to verify if it's SILVER
                        contract_line_end = text.find("\n", start)
                        if contract_line_end == -1:
                            contract_line = text[start:]
                        else:
                            contract_line = text[start:contract_line_end]
                        
                        # Check if this is the Silver contract
                        if "SILVER FUTURES" in contract_line:
                            # Found it. Now define the end of the section.
                            # The section ends at the next "EXCHANGE:" or end of text.
                            # We search for "EXCHANGE:" starting after the current contract line.
                            next_exchange = text.find("EXCHANGE:", contract_line_end)
                            
                            if next_exchange != -1:
                                end = next_exchange
                            else:
                                end = len(text)
                            
                            silver_section = text[start:end]
                            break
                    
                    if silver_section:
                        break

                if not silver_section:
                    return {
                        "error": "COMEX 5000 SILVER FUTURES contract not found",
                        "note": "Market may be closed (holiday/weekend)",
                    }

                # Extract date patterns: MM/DD/YYYY DAILY CUMULATIVE
                # Match lines with date followed by two numbers
                matches = re.findall(
                    r"(\d{1,2}/\d{1,2}/\d{4})\s+([0-9,]+)\s+([0-9,]+)", 
                    silver_section
                )

                if not matches:
                    return {
                        "error": "No delivery data found in COMEX 5000 SILVER FUTURES section"
                    }

                # Get last 3 entries
                last_3_days = []
                for match in matches[-3:]:
                    intent_date = match[0]
                    daily_total = int(match[1].replace(",", ""))
                    cumulative = int(match[2].replace(",", ""))

                    last_3_days.append(
                        {
                            "intent_date": intent_date,
                            "daily_total": daily_total,
                            "total_cumulative": cumulative,
                        }
                    )

                return {
                    "data": last_3_days,
                    "found": True,
                    "source": "CME MTD PDF - COMEX 5000 SILVER FUTURES",
                }

        except Exception as e:
            return {"error": f"Last 3 days parsing error: {str(e)}"}

    def parse_section62_daily_bulletin(self, target_contract_code="MAR26"):
        """
        Parse CME Daily Bulletin Section 62 for Silver data using simplified text analysis.
        Target contract code should be like 'MAR26' (3-letter month + 2-digit year).
        Returns: dict with Price, Change, Volume, OI.
        """
        url = "https://www.cmegroup.com/daily_bulletin/current/Section62_Metals_Futures_Products.pdf"
        pdf_bytes = self.fetch_pdf(url)

        if not pdf_bytes:
            return {"error": "Failed to fetch Daily Bulletin PDF"}

        try:
            with pdfplumber.open(pdf_bytes) as pdf:
                # Find start of SI section
                start_page = -1
                full_text = ""
                
                # Iterate to find the header
                for page in pdf.pages:
                    text = page.extract_text()
                    if "SI FUT" in text:
                        start_page = page.page_number
                        # Capture this page and next 2 pages to be safe
                        full_text += text + "\n"
                        next_p = page.page_number
                        while next_p < len(pdf.pages) and next_p < start_page + 2:
                            full_text += pdf.pages[next_p].extract_text() + "\n"
                            next_p += 1
                        break
                
                if start_page == -1:
                    return {"error": "SI FUT section not found"}

                # Limit to the actual SI FUT section
                lines = full_text.split('\n')
                inside_silver = False
                
                for line in lines:
                    if "SI FUT" in line:
                        inside_silver = True
                    
                    if inside_silver:
                        if "TOTAL SI FUT" in line:
                            if target_contract_code in line: 
                                # Edge case: if target is the last line
                                pass
                            else:
                                break # End of section
                        
                        if target_contract_code in line:
                            # Found the contract line!
                            # Example: MAR26 70.360 77.920 /63.900 76.895 + 0.181 110629 576 76091 - 4411
                            # Extract all numbers, handling commas and decimals and signs
                            
                            # Clean up the line (remove month code)
                            clean_line = line.replace(target_contract_code, "")
                            
                            # Regex to find numbers:
                            # - Integers with commas: 110,629
                            # - Floats: 76.895
                            # - Signed floats: + 0.181 (space might exist)
                            # - Signed ints: - 4411
                            
                            # Normalize spacing around signs
                            clean_line = re.sub(r'([+\-])\s+(\d)', r'\1\2', clean_line)
                            
                            # Extract tokens
                            # Tokens are likely separated by whitespace
                            tokens = clean_line.split()
                            
                            # Filter for numeric tokens
                            nums = []
                            for t in tokens:
                                # Remove common non-numeric chars like '/' or 'B' 'A' (Bid/Ask indicators)
                                t_clean = t.replace('/', '').replace('A', '').replace('B', '').replace(',', '')
                                try:
                                    val = float(t_clean)
                                    nums.append((val, t)) # Keep original text for sign checking
                                except ValueError:
                                    continue
                            
                            if len(nums) >= 4:
                                # Logic:
                                # last 2 are always OI and DeltaOI (signed integer)
                                delta_oi = int(nums[-1][0])
                                oi = int(nums[-2][0])
                                
                                # Search for Price Change among the rest
                                # Price Change is a float, usually small, and OFTEN signed in text (+ 0.181)
                                # Settle is the float immediately preceding it.
                                
                                candidates = nums[:-2]
                                price_change_idx = -1
                                
                                # Iterate backwards to find the Price Change
                                for i in range(len(candidates)-1, -1, -1):
                                    val, text = candidates[i]
                                    # Must be a float (has decimal point)
                                    # Must have sign in text or be small enough (< 5.0)
                                    # To be safe, look for explicit sign OR typical change range
                                    # And check if previous value exists (Settle)
                                    
                                    has_sign = '+' in text or '-' in text
                                    is_float = '.' in text
                                    
                                    if is_float and has_sign:
                                        price_change_idx = i
                                        break
                                
                                if price_change_idx != -1 and price_change_idx > 0:
                                    price_change = candidates[price_change_idx][0]
                                    settle = candidates[price_change_idx-1][0]
                                    
                                    # Volume is sum of ints between PriceChange and OI?
                                    # Identify volume as largest int in between?
                                    # Let's just default volume to 0 or try to pluck it.
                                    volume = 0
                                    # If there are tokens between price_change and OI
                                    vol_candidates = candidates[price_change_idx+1:]
                                    if vol_candidates:
                                        # Take the first one (usually Globex volume)
                                        volume = int(vol_candidates[0][0])

                                    return {
                                        "contract": target_contract_code,
                                        "price": float(settle),
                                        "change": float(price_change),
                                        "volume": volume,
                                        "open_interest": oi,
                                        "delta_oi": delta_oi,
                                        "source": "CME Daily Bulletin PDF"
                                    }

            return {"error": f"Contract {target_contract_code} not found in Silver section"}

        except Exception as e:
            return {"error": f"PDF parsing error: {e}"}




if __name__ == "__main__":
    parser = CMEDeliveryParser()

    print("=" * 60)
    print("Testing CME Last 3 Days Silver Deliveries")
    print("=" * 60)
    last_3 = parser.parse_last_3_days_silver()
    
    if "data" in last_3:
        print("✅ Successfully extracted delivery data:")
        for entry in last_3["data"]:
            print(f"  • {entry['intent_date']}: {entry['daily_total']} daily, {entry['total_cumulative']} cumulative")
        print(f"\nSource: {last_3['source']}")
    else:
        print(f"❌ Error: {last_3.get('error')}")
        if 'note' in last_3:
            print(f"   Note: {last_3['note']}")

    print("\n" + "=" * 60)
    print("Testing CME Daily Issues & Stops Parser")
    print("=" * 60)
    daily = parser.parse_daily_issues_stops()
    print(f"Daily Result:")
    for key, value in daily.items():
        print(f"  {key}: {value}")

    print("\n" + "=" * 60)
    print("Testing CME MTD Deliveries Parser")
    print("=" * 60)
    mtd = parser.parse_mtd_deliveries()
    print(f"MTD Result:")
    for key, value in mtd.items():
        print(f"  {key}: {value}")
