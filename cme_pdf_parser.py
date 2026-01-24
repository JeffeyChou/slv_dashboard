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

                full_text = ""
                for page in pdf.pages:
                    full_text += page.extract_text() + "\n"

                # Find month
                month_match = re.search(
                    r"(JANUARY|FEBRUARY|MARCH|APRIL|MAY|JUNE|JULY|AUGUST|SEPTEMBER|OCTOBER|NOVEMBER|DECEMBER)\s+(\d{4})",
                    full_text,
                    re.IGNORECASE,
                )
                if month_match:
                    mtd_data["month"] = (
                        f"{month_match.group(1).title()} {month_match.group(2)}"
                    )

                # Find MTD totals for silver
                # Look for "MONTH TO DATE:" after silver contract section
                silver_mtd = re.finditer(
                    r"(SILVER FUTURES|COMEX 5000 SILVER|5000 SILVER).*?"
                    r"MONTH TO DATE:\s*(\d+)",
                    full_text,
                    re.DOTALL | re.IGNORECASE,
                )

                for match in silver_mtd:
                    mtd_total = int(match.group(2))
                    mtd_data["mtd_issued"] += mtd_total
                    mtd_data["mtd_stopped"] += mtd_total  # Usually same for MTD
                    mtd_data["found"] = True

                if not mtd_data["found"]:
                    return {
                        "error": "No MTD silver data found",
                        "month": mtd_data.get("month"),
                        "note": "Market may be closed or start of new month",
                    }

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
                    
                    # Look for CONTRACT line that contains SILVER
                    if re.search(r"CONTRACT:.*SILVER FUTURES", text):
                        # Extract from CONTRACT: to next EXCHANGE: or end
                        start = text.find("CONTRACT:")
                        if start == -1:
                            continue
                        
                        # Verify this CONTRACT line is actually for SILVER
                        contract_line_end = text.find("\n", start)
                        contract_line = text[start:contract_line_end]
                        if "SILVER" not in contract_line:
                            continue
                        
                        # Find end marker (next contract or end of page)
                        end = len(text)
                        next_exchange = text.find("EXCHANGE:", start + 100)
                        if next_exchange != -1:
                            end = next_exchange
                        
                        silver_section = text[start:end]
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
