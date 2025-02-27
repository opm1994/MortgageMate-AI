import streamlit as st
import fitz  # PyMuPDF for PDF text extraction
import re
import pandas as pd
from fpdf import FPDF
from io import BytesIO

# Function to extract text from PDF files
def extract_text_from_pdf(uploaded_file):
    doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
    text = "\n".join([page.get_text("text") for page in doc])
    return text

# Function to extract key underwriting details
def extract_income(text, borrower_type):
    if borrower_type == "Self-Employed":
        match = re.search(r"Total Deposits: \$([\d,]+)", text)
        stated_income_match = re.search(r"Stated Personal Business Income: \$([\d,]+)", text)
    else:
        match = re.search(r"Salary Rate: \$([\d,]+)", text)
        t4_income_match = re.search(r"T4 Line 15000: \$([\d,]+)", text)
    
    income_values = [int(m.group(1).replace(",", "")) for m in [match, stated_income_match, t4_income_match] if m]
    return max(income_values) if income_values else 0

def extract_credit_score(text):
    match = re.search(r"Credit Score: (\d+)", text)
    return int(match.group(1)) if match else 0

def extract_down_payment(text):
    match = re.search(r"Down Payment: \$([\d,]+)", text)
    return int(match.group(1).replace(",", "")) if match else 0

def extract_liabilities(text):
    liabilities = []
    pattern = r"(Credit Card|Loan|Line of Credit):\s+\$([\d,]+)"
    matches = re.findall(pattern, text)
    for match in matches:
        debt_type = match[0]
        amount = int(match[1].replace(",", ""))
        payment = amount * 0.03 if "Credit Card" in debt_type else amount * 0.02 if "Line of Credit" in debt_type else amount / 60
        liabilities.append({"Type": debt_type, "Amount": amount, "Monthly Payment": round(payment, 2)})
    return liabilities

def calculate_ratios(gross_income, mortgage_pmt, heat, other_debts, stress_test_rate):
    qualified_mortgage_pmt = mortgage_pmt * (1 + (stress_test_rate / 100))
    gds = ((qualified_mortgage_pmt + heat) / gross_income) * 100
    tds = ((qualified_mortgage_pmt + heat + other_debts) / gross_income) * 100
    return {"GDS": round(gds, 2), "TDS": round(tds, 2)}

def match_lender(gds, tds, credit_score, down_payment, borrower_type):
    if gds <= 39 and tds <= 44 and credit_score >= 680 and down_payment >= 20:
        return "Prime Lender"
    elif gds <= 46.3 and tds <= 46.3 and borrower_type == "Self-Employed":
        return "Community Trust (Alternative Lender)"
    elif gds <= 50 and tds <= 50:
        return "B Lender"
    else:
        return "Private Lender Needed"

def generate_underwriting_explanation(gds, tds, credit_score, down_payment, borrower_type):
    explanation = "This file was underwritten based on the following factors: "
    explanation += f"Income was calculated based on borrower type ({borrower_type}). "
    explanation += f"GDS and TDS ratios were determined as {gds}% and {tds}% respectively. "
    explanation += f"Credit score of {credit_score} was considered for lender eligibility. "
    explanation += f"A down payment of ${down_payment:,} was factored into LTV calculations. "
    explanation += f"Based on these factors, the AI determined the best lender match to be: {match_lender(gds, tds, credit_score, down_payment, borrower_type)}."
    return explanation

st.title("MortgageMate AI - Automated Underwriting")

borrower_type = st.selectbox("What is the borrower's employment type?", ["Salaried", "Self-Employed", "Commission-Based", "Other"])
interest_rate_type = st.selectbox("What type of interest rate is the borrower choosing?", ["Fixed", "Variable"])
amortization_period = st.selectbox("What is the amortization period?", ["25 Years", "30 Years", "Other"])

uploaded_file = st.file_uploader("Upload Mortgage Documents", type=["pdf"])
if uploaded_file:
    text = extract_text_from_pdf(uploaded_file)
    
    income = extract_income(text, borrower_type)
    credit_score = extract_credit_score(text)
    down_payment = extract_down_payment(text)
    liabilities = extract_liabilities(text)
    
    mortgage_pmt = 5090
    heat = 100
    other_debts = sum(liability["Monthly Payment"] for liability in liabilities) if liabilities else 0
    stress_test_rate = 5.25
    
    ratios = calculate_ratios(income, mortgage_pmt, heat, other_debts, stress_test_rate)
    lender = match_lender(ratios["GDS"], ratios["TDS"], credit_score, down_payment, borrower_type)
    explanation = generate_underwriting_explanation(ratios["GDS"], ratios["TDS"], credit_score, down_payment, borrower_type)
    
    underwriting_summary = {
        "Borrower Type": borrower_type,
        "Income": f"${income:,}",
        "Credit Score": credit_score,
        "Down Payment": f"${down_payment:,}",
        "GDS": f"{ratios['GDS']}%",
        "TDS": f"{ratios['TDS']}%",
        "Lender Matched": lender,
        "Underwriting Explanation": explanation
    }
    
    st.write(underwriting_summary)
    
    if st.button("Download Underwriting Report as PDF"):
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=12)
        for key, value in underwriting_summary.items():
            pdf.cell(200, 10, txt=f"{key}: {value}", ln=True)
        pdf.output("underwriting_report.pdf")
        with open("underwriting_report.pdf", "rb") as file:
            st.download_button(label="Download PDF", data=file, file_name="underwriting_report.pdf", mime="application/pdf")
