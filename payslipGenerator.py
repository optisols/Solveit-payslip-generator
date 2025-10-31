#!/usr/bin/env python3
"""
Payslip generator - final version

- Prompts for company name, address, payslip month,locaton of EMployees and salary register location.
- Reads Excel with header row = Excel row 3 (pandas header=2).
- Generates one PDF per employee with pixel-tuned layout.
- Packs all PDFs into Payslips_<month>_<timestamp>.zip.
- Uses logging to payslip_generator.log and console.
"""

import os
import sys
import io
import csv
import re
import math
import zipfile
import glob
import logging
import tempfile
import shutil
import argparse
import json
import time
import concurrent.futures
from datetime import datetime
from decimal import Decimal, InvalidOperation

import pandas as pd
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from dateutil import parser as dateparser

# --------- LOGGER SETUP ----------
LOG_FILENAME = "payslip_generator.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILENAME, mode="a", encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("PayslipGenerator")

# -------- FONT CONFIG ------------
FONT_FILE = "DejaVuSans.ttf"   # set to None if you don't have it
FALLBACK_FONT = "Helvetica"
FONT_NAME = FALLBACK_FONT
try:
    if FONT_FILE and os.path.exists(FONT_FILE):
        pdfmetrics.registerFont(TTFont("CustomFont", FONT_FILE))
        FONT_NAME = "CustomFont"
        logger.info(f"Using custom font: {FONT_FILE}")
    else:
        FONT_NAME = FALLBACK_FONT
        logger.info("Using fallback font: Helvetica")
except Exception as e:
    FONT_NAME = FALLBACK_FONT
    logger.warning(f"Could not register font. Falling back to Helvetica. Error: {e}")

# -------- COLUMN MAPPING ---------
COL_CANDIDATES = {
    "EmployeeName": ["Employee Name", "EmployeeName", "Name"],
    "Ecode": ["E code", "Ecode", "Emp Code", "ecode"],
    "Designation": ["Designation"],
    "Department": ["Department"],
    "FatherName": ["Father / Husband Name", "FatherName", "Father"],
    "DOB": ["DOB", "Date of Birth"],
    "Location": ["Location"],
    "UAN": ["UAN"],
    "ESI_No": ["Esi No", "ESI No", "ESI_No"],
    "PAN_No": ["PAN No", "PAN"],
    "DOJ": ["DOJ", "Date of Joining"],
    "PaidDays": ["Paid Days", "PaidDays"],
    "LOP": ["LOP", "Loss of Pay"],
    "PayMode": ["Pay Mode", "PayMode"],
    "BankName": ["Bank name", "BankName"],
    "AccountNo": ["Account No", "AccountNo"],
    "PL": ["PL"],
    "SL": ["SL"],
    "CL": ["CL"],
    "Basic": ["Basic"],
    "SpecialAllowance": ["Special Allowance", "Special Allownace", "SpecialAllowance"],
    "TravelAllowance": ["Travel Allowance", "TravelAllowance"],
    "HRA": ["House Rent Allowance", "HRA"],
    "NH_FH": ["NH/FH", "NH_FH"],
    "Reimbursement": ["Reimbursement", "Reimbursement"],
    "EPF": ["EPF"],
    "ESI": ["ESI"],
    "PT": ["PT"],
    "TDS": ["TDS"],
    "Adv_Other": ["Adv/Other", "Adv_Other", "Advance"],
    "LabourWelfareFund": ["Labour Welfare Fund", "LabourWelfareFund"]
}

# -------- UTILS ---------
def find_column(df_cols, candidates):
    lower_map = {c.lower(): c for c in df_cols}
    for cand in candidates:
        if not cand:
            continue
        key = cand.lower()
        if key in lower_map:
            return lower_map[key]
    return None

def build_col_map(df):
    mapping = {}
    for key, candidates in COL_CANDIDATES.items():
        mapping[key] = find_column(df.columns, candidates)
    return mapping

def safe_val(row, colname, default=""):
    if not colname:
        return default
    val = row.get(colname, default)
    if pd.isna(val):
        return default
    return val

def to_number(val):
    if val is None or val == "":
        return 0.0
    try:
        if isinstance(val, str):
            v = val.replace(",", "").strip()
            if v == "":
                return 0.0
            return float(v)
        return float(val)
    except Exception:
        try:
            return float(str(val))
        except:
            return 0.0

def moneyfmt(val):
    try:
        d = Decimal(str(val))
        return f"{d:,.2f}"
    except (InvalidOperation, Exception):
        return "0.00"

def normalize_date(val):
    if val in (None, ""):
        return ""
    try:
        if isinstance(val, pd.Timestamp):
            return val.strftime("%d-%m-%Y")
        return dateparser.parse(str(val)).strftime("%d-%m-%Y")
    except Exception:
        return str(val)

# -------- PDF DRAWING (pixel-perfect) ---------
def draw_payslip_to_bytes(header_info, data):
    """
    Return PDF bytes (in-memory) for one payslip using layout tuned to the screenshots.
    - Shows PL / SL / CL values in PAYMENT & LEAVE BALANCES box
    - Draws small rounded light-blue stat boxes: Work days, India, Overseas, LOP, Secondment
    """
    buffer = io.BytesIO()
    W, H = A4
    c = canvas.Canvas(buffer, pagesize=A4)
    margin = 12 * mm

    # Outer thick border
    c.setLineWidth(2)
    c.setStrokeColor(colors.black)
    c.rect(margin, margin, W - 2*margin, H - 2*margin)

    # Header company name & address (moved down a bit to avoid collision with top border)
    top_y = H - margin - 26
    c.setFont(FONT_NAME, 18)
    c.setFillColor(colors.HexColor("#0074D9"))  # blue company name (optional)
    c.drawCentredString(W/2, top_y, header_info.get("company", ""))
    # --- Wrapped, centered address lines ---
    c.setFont(FONT_NAME, 9)
    c.setFillColor(colors.black)
    address_text = header_info.get("address", "") or ""

    # compute available width for address: slightly narrower than page width to avoid touching border
    address_margin = 40  # left+right margin for address area in points (adjust if needed)
    max_addr_width = W - 2 * (margin + address_margin)

    # helper: wrap text to fit in max_width using pdfmetrics.stringWidth
    def wrap_text_to_width(text, font_name, font_size, max_width):
        words = str(text).split()
        if not words:
            return []
        lines = []
        cur = words[0]
        for w in words[1:]:
            test = cur + " " + w
            if pdfmetrics.stringWidth(test, font_name, font_size) <= max_width:
                cur = test
            else:
                lines.append(cur)
                cur = w
        lines.append(cur)
        return lines
    
    address_lines = wrap_text_to_width(address_text, FONT_NAME, 9, max_addr_width)

    # draw each wrapped line centered under the company name
    # start a little lower than the company name (top_y - 14 as before)
    addr_start_y = top_y - 14
    line_height = 11  # approx font size + small leading
    for i, line in enumerate(address_lines):
        c.drawCentredString(W/2, addr_start_y - i * line_height, line)
 

    # Payslip month
    c.setFont(FONT_NAME, 10)
    c.drawString(margin + 6, top_y - 36, f"Payslip for the Month :  {header_info.get('month','')}")
    #logger.info("=== after month ===")
    #logger.info(f"Location value: {header_info.get('location','')}")


    # EMPLOYEE DETAILS box (enlarged so DOB fits)
    box_x = margin + 6
    box_w = W - 2*(margin + 6)
    box_top = top_y - 46
    box_h = 80   # enlarged to fit DOB properly
    c.setLineWidth(1)
    c.rect(box_x, box_top - box_h, box_w, box_h)

    # vertical split for columns
    left_w = box_w * 0.61
    c.line(box_x + left_w, box_top - box_h, box_x + left_w, box_top)

    # left column contents
    x_left = box_x + 8
    y = box_top - 14
    c.setFont(FONT_NAME, 9)
    c.drawString(x_left, y, "Employee Name")
    c.drawString(x_left + 110, y, str(data.get("EmployeeName","")))
    y -= 12
    c.drawString(x_left, y, "E code")
    c.drawString(x_left + 110, y, str(data.get("Ecode","")))
    y -= 12
    c.drawString(x_left, y, "Designation")
    c.drawString(x_left + 110, y, str(data.get("Designation","")))
    y -= 12
    c.drawString(x_left, y, "Department")
    c.drawString(x_left + 110, y, str(data.get("Department","")))
    y -= 12
    c.drawString(x_left, y, "Father / Husband Name")
    c.drawString(x_left + 110, y, str(data.get("FatherName","")))
    y -= 12
    c.drawString(x_left, y, "DOB")
    c.drawString(x_left + 110, y, str(data.get("DOB","")))

    # right column contents
    rx = box_x + left_w + 11
    ry = box_top - 14
    c.drawString(rx, ry, "Location")
    c.drawString(rx + 70, ry, str(header_info.get("location","")))
    #logger.info(f"Location value: {header_info.get('location','')}") # Debug log for location
    ry -= 12
    # UAN default to 'NIL' if blank
    UAN_val = data.get("UAN", "")
    if UAN_val in ("", None) or (isinstance(UAN_val, float) and pd.isna(UAN_val)):
        data["UAN"] = "NIL"
    if isinstance(UAN_val, float) and UAN_val.is_integer():
        data["UAN"] = str(int(UAN_val))
    c.drawString(rx, ry, "UAN")
    c.drawString(rx + 70, ry, str(data.get("UAN","")))
    ry -= 12
    c.drawString(rx, ry, "Esi No")
    c.drawString(rx + 70, ry, str(data.get("ESI_No","")))
    ry -= 12
    c.drawString(rx, ry, "PAN No")
    c.drawString(rx + 70, ry, str(data.get("PAN_No","")))
    ry -= 12
    c.drawString(rx, ry, "DOJ")
    c.drawString(rx + 70, ry, str(data.get("DOJ","")))

    # PAYMENT & LEAVE BALANCES box under employee details (enlarged)
    pl_top = box_top - box_h - 8
    pl_h = 70   # slightly larger for PL/SL/CL & account lines
    c.rect(box_x, pl_top - pl_h, box_w, pl_h)
    c.setFont(FONT_NAME, 9)
    c.drawString(box_x + 6, pl_top - 14, "PAYMENT & LEAVE BALANCES")

    # Paid Days and LOP (default LOP->0 if blank)
    lop_val = data.get("LOP", "")
    if lop_val in ("", None) or (isinstance(lop_val, float) and pd.isna(lop_val)):
        data["LOP"] = "0"
    paid_days_val = data.get("PaidDays", "")
    c.drawRightString(box_x + box_w * 0.80 + 8, pl_top - 14, f"Paid Days  {paid_days_val}    LOP  {data.get('LOP','')}")

    # left area details: Pay Mode / Bank name / Account No
    c.drawString(box_x + 6, pl_top - 30, "Pay Mode")
    c.drawString(box_x + 66, pl_top - 30, str(data.get("PayMode","")))
    c.drawString(box_x + 6, pl_top - 46, "Bank name")
    c.drawString(box_x + 66, pl_top - 46, str(data.get("BankName","")))
    c.drawString(box_x + 6, pl_top - 62, "Account No")
    # ensure account no doesn't get clipped - format as string and trim trailing .0 from floats
    acc = data.get("AccountNo", "")
    if isinstance(acc, float) and acc.is_integer():
        acc = str(int(acc))
    else:
        acc = str(acc)
    c.drawString(box_x + 66, pl_top - 62, str(acc))

    # Earnings & Deductions big box
    ed_top = pl_top - pl_h - 10
    ed_h = 220
    c.rect(box_x, ed_top - ed_h, box_w, ed_h)

    # header band for columns (blue)
    header_h = 18
    c.setFillColor(colors.HexColor("#7fb0d6"))
    c.rect(box_x, ed_top - header_h, box_w, header_h, stroke=0, fill=1)
    c.setFillColor(colors.black)
    c.setFont(FONT_NAME, 10)
    c.drawString(box_x + 8, ed_top - header_h + 4, "Earnings")
    c.drawString(box_x + box_w * 0.53 , ed_top - header_h + 4, "Amount")
    c.drawString(box_x + box_w * 0.62 + 8, ed_top - header_h + 4, "Deduction")
    c.drawString(box_x + box_w - 52, ed_top - header_h + 4, "Amount")

    # columns coordinates
    left_col_x = box_x + 8
    amt_x = box_x + box_w * 0.48 + 60
    ded_col_x = box_x + box_w * 0.62 + 8
    ded_amt_x = box_x + box_w - 20

    # Earnings rows
    c.setFont(FONT_NAME, 9)
    y_row = ed_top - header_h - 12
    earnings_rows = [
        ("Basic", data.get("Basic", 0.0)),
        ("Special Allowance", data.get("SpecialAllowance", 0.0)),
        ("Travel Allowance", data.get("TravelAllowance", 0.0)),
        ("House Rent Allowance", data.get("HRA", 0.0)),
        ("NH/FH", data.get("NH_FH", 0.0)),
        ("Reimbursement", data.get("Reimbursement", 0.0)),
    ]
    for label, val in earnings_rows:
        c.drawString(left_col_x, y_row, label)
        c.drawRightString(amt_x, y_row, moneyfmt(val))
        y_row -= 14

    # Gross
    gross = sum([float(data.get(k, 0) or 0) for k in ["Basic","SpecialAllowance","TravelAllowance","HRA","NH_FH","Reimbursement"]])
    c.setFont(FONT_NAME, 10)
    c.drawString(left_col_x, ed_top - ed_h + 12, "Gross Earnings")
    c.drawRightString(amt_x, ed_top - ed_h + 12, moneyfmt(gross))

    # Deductions rows
    c.setFont(FONT_NAME, 9)
    dy = ed_top - header_h - 12
    deductions_rows = [
        ("EPF", data.get("EPF", 0.0)),
        ("ESI", data.get("ESI", 0.0)),
        ("PT", data.get("PT", 0.0)),
        ("TDS", data.get("TDS", 0.0)),
        ("Adv/Other", data.get("Adv_Other", 0.0)),
        ("Labour Welfare Fun", data.get("LabourWelfareFund", 0.0)),
    ]
    for label, val in deductions_rows:
        c.drawString(ded_col_x, dy, label)
        c.drawRightString(ded_amt_x, dy, moneyfmt(val))
        dy -= 14

    total_ded = sum([float(data.get(k, 0) or 0) for k in ["EPF","ESI","PT","TDS","Adv_Other","LabourWelfareFund"]])
    c.setFont(FONT_NAME, 10)
    c.drawString(ded_col_x, ed_top - ed_h + 12, "Total Deductions")
    c.drawRightString(ded_amt_x, ed_top - ed_h + 12, moneyfmt(total_ded))

    # Draw table grid for Earnings/Deductions columns
    num_rows = max(len(earnings_rows), len(deductions_rows))
    row_height = ed_h / (num_rows + 2)  # +2 for Gross/Total rows
    table_top = ed_top
    table_left = box_x
    table_width = box_w
    table_height = row_height * (num_rows + 2)  # +2 for Gross/Total rows

    # Draw vertical lines
    c.setLineWidth(0.5)
    c.line(table_left, table_top, table_left, table_top - table_height)
    c.line(amt_x + 8, table_top, amt_x + 8, table_top - table_height)
    #c.line(ded_col_x - 4, table_top, ded_col_x - 4, table_top - table_height)
    #c.line(ded_amt_x + 4, table_top, ded_amt_x + 4, table_top - table_height)
    c.line(table_left + table_width, table_top, table_left + table_width, table_top - table_height)

    # Draw horizontal lines only for header and footer (Gross/Total rows)
    # Header line
    c.line(table_left, ed_top, table_left + table_width, ed_top)
    c.line(table_left, ed_top - header_h, table_left + table_width, ed_top - header_h)
    # Gross Earnings and Total Deductions row line (footer)
    gross_footer_y = ed_top - ed_h + 25  # Adjust as needed for alignment
    c.line(table_left, gross_footer_y, table_left + table_width, gross_footer_y)



    # Net Pay footer
    net = gross - total_ded
    footer_y = ed_top - ed_h - 28
    c.setLineWidth(1.5)
    c.line(box_x, footer_y + 28, box_x + box_w, footer_y + 28)
    c.setFont(FONT_NAME, 12)
    c.drawString(box_x + 10, footer_y + 8, f"Total Net Payable Rs.{moneyfmt(net)}/-")
    c.setFont(FONT_NAME, 8)
    c.drawRightString(box_x + box_w - 10, footer_y + 8, "(Net Payable = Gross Earnings - Total Deductions)")

    # small footer identity
    c.setFont(FONT_NAME, 8)
    c.drawString(box_x + 10, margin + 8, f"Employee: {data.get('EmployeeName','')}   Ecode: {data.get('Ecode','')}")
    c.showPage()
    c.save()

    buffer.seek(0)
    return buffer.read()


# -------- PROCESS & ZIP ---------
def process_file(file_path, company, address, month, location):
    if not os.path.exists(file_path):
        logger.error(f"Salary register file not found: {file_path}")
        return

    try:
        # When reading the Excel file
        df = pd.read_excel(file_path, header=2, engine="openpyxl", dtype={"Account No": str, "AccountNo": str})
        logger.info(f"Loaded salary register: {file_path} (rows: {len(df)})")
    except Exception as e:
        logger.exception("Error reading Excel file")
        return

    mapping = build_col_map(df)
    logger.debug(f"Column mapping: {mapping}")

    base_dir = os.path.dirname(os.path.abspath(file_path)) or "."
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_month = "".join(ch for ch in month if ch.isalnum() or ch in (" ", "_")).replace(" ", "_")
    zip_name = os.path.join(base_dir, f"Payslips_{safe_month}_{timestamp}.zip")
    zipf = zipfile.ZipFile(zip_name, "w", zipfile.ZIP_DEFLATED)

    count = 0
    for idx, row in df.iterrows():
        if row.isnull().all():
            continue
        #Build data
        data = {}
        for key, colname in mapping.items():
            data[key] = safe_val(row, colname, "")
        #normalize numarics
        for n in ["Basic","SpecialAllowance","TravelAllowance","HRA","NH_FH","Reimbursement",
                  "EPF","ESI","PT","TDS","Adv_Other","LabourWelfareFund"]:
            data[n] = to_number(data.get(n, 0))
        #Date normalization
        data["DOB"] = normalize_date(data.get("DOB",""))
        data["DOJ"] = normalize_date(data.get("DOJ",""))
        #Defaults for missing fields
        data.setdefault("PaidDays","")
        data.setdefault("LOP","")
        data.setdefault("PayMode","")
        data.setdefault("BankName","")
        data.setdefault("AccountNo","")
        data.setdefault("EmployeeName","")
        data.setdefault("Ecode","")

        ecode = str(data.get("Ecode","")).strip() or f"row{idx+4}"
        name = str(data.get("EmployeeName","")).strip() or "Unknown"
        safe_name = "_".join(name.split())
        pdf_filename = f"Payslip_{ecode}_{safe_name}.pdf"

        try:
            pdf_bytes = draw_payslip_to_bytes(
                {"company": company, "address": address, "month": month, "location": location}, data
            )
            zipf.writestr(pdf_filename, pdf_bytes)
            count += 1
            logger.info(f"Added to ZIP: {pdf_filename}")
        except Exception as e:
            logger.exception(f"Failed creating payslip for row {idx+4} ({name})")


    zipf.close()
    logger.info(f"Done. Generated {count} payslips and saved ZIP: {zip_name}")

# -------- MAIN ---------
import argparse

def parse_args():
    parser = argparse.ArgumentParser(description="Generate payslips")
    parser.add_argument("--company", help="Company name")
    parser.add_argument("--address", help="Company address")
    parser.add_argument("--month", help="Payslip month (e.g. 'August 2025')")
    parser.add_argument("--location", help="Work location of employees")
    parser.add_argument("--salary", help="Path to salary register file (e.g. SALARY REG.xlsm)")
    return parser.parse_args()

def main():
    logger.info("=== Payslip Generator Started ===")
    args = parse_args()

    # Interactive fallback (when arguments are not passed)
    if not any([args.company, args.address, args.month, args.location, args.salary]):
        logger.info("No command-line arguments detected. Running in interactive mode.")
        company = input("1. Company name: ").strip()
        address = input("2. Company address: ").strip()
        month = input("3. Payslip for the month (e.g. 'August 2025'): ").strip()
        location = input("4. Work Location of Employees : ").strip() 
        file_path = input("5. Location of the salary register (path to SALARY REG.xlsm): ").strip()
    else:
        # Non-interactive CLI mode (for Flask integration)
        company = args.company
        address = args.address
        month = args.month
        location = args.location
        file_path = args.salary

    if not company or not address or not month or not file_path:
        logger.error("All inputs required. Exiting.")
        sys.exit(1)

    logger.info(f"Company: {company}, Month: {month}, Location: {location}")
    logger.info(f"Salary file: {file_path}")

    process_file(file_path, company, address, month, location)
    logger.info("=== Payslip Generator Finished ===")

if __name__ == "__main__":
    main()
