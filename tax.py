import streamlit as st
import pandas as pd
from datetime import datetime
from PIL import Image
from fpdf import FPDF
import os
import uuid  # For generating unique filenames

# Define directories for storing data and images
DATA_DIR = 'data'
IMAGES_DIR = os.path.join(DATA_DIR, 'receipts')

# Create directories if they don't exist
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(IMAGES_DIR, exist_ok=True)

# Function to save data to a CSV file
def save_expenses_to_csv(data, filename=os.path.join(DATA_DIR, 'expenses.csv')):
    df = pd.DataFrame(data)
    df.to_csv(filename, index=False)

# Function to load data from a CSV file
def load_expenses_from_csv(filename=os.path.join(DATA_DIR, 'expenses.csv')):
    if os.path.exists(filename):
        return pd.read_csv(filename).to_dict('records')
    else:
        return []

# Function to generate a PDF report
def generate_pdf(expenses, filename='Expense_Report.pdf'):
    pdf = FPDF()
    pdf.add_page()
    
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, txt="Work-Related Expense Report", ln=True, align='C')

    # Table header
    pdf.set_font("Arial", 'B', size=10)
    pdf.cell(40, 10, "Date", border=1)
    pdf.cell(40, 10, "Type", border=1)
    pdf.cell(60, 10, "Description", border=1)
    pdf.cell(40, 10, "Amount (R)", border=1)
    pdf.ln()

    # Table data
    pdf.set_font("Arial", size=10)
    for expense in expenses:
        pdf.cell(40, 10, expense["Date"], border=1)
        pdf.cell(40, 10, expense["Type"], border=1)
        pdf.cell(60, 10, expense["Description"], border=1)
        pdf.cell(40, 10, f"R{expense['Amount (R)']:.2f}", border=1)
        pdf.ln()

    # Save the PDF to file
    pdf.output(filename)

# Load previous expenses from CSV
if 'expenses' not in st.session_state:
    st.session_state['expenses'] = load_expenses_from_csv()

st.title("Work-Related Expense and Tax Calculator")
st.write("Track your work-related expenses, logbook, and calculate potential tax deductions.")

# **Personal Details and Income Entry**
with st.expander("Income and Contributions Details", expanded=True):
    st.info("Provide details about your income and contributions for the tax year.")
    
    gross_income = st.number_input("Annual Gross Income (R)", min_value=0.0, format="%.2f", help="Your total earnings for the year before tax.")
    retirement_contributions = st.number_input("Retirement Contributions (R)", min_value=0.0, format="%.2f", help="Contributions to pension, provident, or retirement annuities.")
    medical_aid_contributions = st.number_input("Medical Aid Contributions (R)", min_value=0.0, format="%.2f", help="Your monthly medical aid payments.")
    other_contributions = st.number_input("Other Tax-Deductible Contributions (R)", min_value=0.0, format="%.2f", help="Charitable donations, professional fees, etc.")
    travel_allowance = st.number_input("Travel Allowance (R)", min_value=0.0, format="%.2f", help="Any work-related travel allowance you receive.")

# **Expense entry form**
st.subheader("Add New Expense")
expense_type = st.selectbox("Expense Type", ["Transport", "Lunch", "Office Supplies", "Home Office", "Other"])
expense_description = st.text_input("Expense Description")
expense_amount = st.number_input("Expense Amount (R)", min_value=0.0, format="%.2f")
expense_date = st.date_input("Expense Date", value=datetime.today())

# File uploader for receipts
receipt_file = st.file_uploader("Upload Receipt (optional)", type=["jpg", "jpeg", "png"])

# Add expense button
if st.button("Add Expense"):
    # Store the expense data
    if receipt_file:
        # Save the uploaded receipt image to disk
        unique_filename = str(uuid.uuid4()) + "_" + receipt_file.name
        receipt_path = os.path.join(IMAGES_DIR, unique_filename)
        with open(receipt_path, 'wb') as out_file:
            out_file.write(receipt_file.read())
    else:
        receipt_path = None

    new_expense = {
        "Date": expense_date.strftime('%Y-%m-%d'),
        "Type": expense_type,
        "Description": expense_description,
        "Amount (R)": expense_amount,
        "Receipt": receipt_path
    }
    st.session_state['expenses'].append(new_expense)
    save_expenses_to_csv(st.session_state['expenses'])
    st.success("Expense added successfully!")

# **Display the list of expenses**
if st.session_state['expenses']:
    st.subheader("Logged Expenses")
    df = pd.DataFrame(st.session_state['expenses'])
    st.dataframe(df[['Date', 'Type', 'Description', 'Amount (R)']])

# **Uncommon Deductions Entry Form**
with st.expander("Uncommon Deductions", expanded=True):
    st.info("Provide details for uncommon but potentially beneficial deductions.")
    
    disability_expenses = st.number_input("Disability-Related Expenses (R)", min_value=0.0, format="%.2f", help="Expenses related to disability, e.g., medical aids, therapies, and equipment.")
    work_clothing = st.number_input("Work-Related Clothing (R)", min_value=0.0, format="%.2f", help="Clothing specifically required for work and not wearable outside of work.")
    professional_fees = st.number_input("Professional Fees (R)", min_value=0.0, format="%.2f", help="Accounting, legal, or consulting fees for your business.")
    childcare_costs = st.number_input("Childcare Costs (R)", min_value=0.0, format="%.2f", help="Childcare expenses while you're working.")
    donations_political = st.number_input("Donations to Political Parties (R)", min_value=0.0, format="%.2f", help="Donations made to registered political parties.")
    interest_on_loans = st.number_input("Interest on Loans for Investments (R)", min_value=0.0, format="%.2f", help="Interest on loans used to acquire investment assets.")
    investment_losses = st.number_input("Losses from Investments (R)", min_value=0.0, format="%.2f", help="Losses from the sale of investment assets.")
    bad_debts = st.number_input("Bad Debts (R)", min_value=0.0, format="%.2f", help="Loans that are deemed irrecoverable and count as bad debts.")

# **Logbook for Travel**
with st.expander("Logbook for Travel Deductions", expanded=False):
    st.info("Keep a record of your business-related travel. Ensure to maintain a logbook for SARS compliance.")
    travel_distance = st.number_input("Business Travel Distance (km)", min_value=0.0, format="%.1f")
    travel_description = st.text_input("Description of Business Travel")
    travel_date = st.date_input("Travel Date", value=datetime.today())
    
    if st.button("Add to Logbook"):
        new_travel_entry = {
            "Date": travel_date.strftime('%Y-%m-%d'),
            "Description": travel_description,
            "Distance (km)": travel_distance
        }
        if 'logbook' not in st.session_state:
            st.session_state['logbook'] = []
        st.session_state['logbook'].append(new_travel_entry)
        st.success("Travel entry added successfully!")

    if 'logbook' in st.session_state and st.session_state['logbook']:
        st.subheader("Logged Business Travel")
        df_logbook = pd.DataFrame(st.session_state['logbook'])
        st.dataframe(df_logbook)

# **Calculate Potential Total Deductions Including Uncommon Deductions**
st.subheader("Total Claimable Deductions from SARS")

# Calculate total uncommon deductions
total_uncommon_deductions = (disability_expenses + work_clothing + professional_fees +
                             childcare_costs + donations_political + interest_on_loans +
                             investment_losses + bad_debts)

# Calculate total common deductions
total_expenses = sum([expense['Amount (R)'] for expense in st.session_state['expenses']])
total_common_deductions = total_expenses + retirement_contributions + other_contributions + travel_allowance

# Combine all deductions
total_deductions = total_common_deductions + total_uncommon_deductions

# Apply deduction limitations
retirement_limit = min(retirement_contributions, 0.275 * gross_income, 350000)
medical_aid_credit = 0.25 * medical_aid_contributions  # Rough estimate for illustration
total_deductions = min(total_deductions, gross_income)  # Ensure deductions don't exceed income

# Display the total deductions and potential claim back
st.write(f"Total Common Deductions: R{total_common_deductions:.2f}")
st.write(f"Total Uncommon Deductions: R{total_uncommon_deductions:.2f}")
st.write(f"Total Deductible Amount: R{total_deductions:.2f}")

# **Display Calculations Tab (Latex)**
with st.expander("View Tax Calculation Details (LaTeX)"):
    st.latex(r'''
    \text{Total Deductions} = \text{Common Deductions} + \text{Uncommon Deductions}
    ''')
    st.latex(r'''
    \text{Total Claimable Deductions} = \min(\text{Total Deductions}, \text{Gross Income})
    ''')

# **PDF report download**
if st.button("Download PDF Report"):
    generate_pdf(st.session_state['expenses'])
    with open("Expense_Report.pdf", "rb") as pdf_file:
        st.download_button("Download PDF", pdf_file, file_name="Expense_Report.pdf")

# **Receipt Display**
st.subheader("View Receipts")
for expense in st.session_state['expenses']:
    if expense['Receipt'] and os.path.exists(expense['Receipt']):
        st.write(f"Receipt for {expense['Description']} (R{expense['Amount (R)']:.2f})")
        receipt_image = Image.open(expense['Receipt'])
        st.image(receipt_image, caption="Uploaded Receipt", use_column_width=True)
    elif expense['Receipt'] and not os.path.exists(expense['Receipt']):
        st.write(f"Receipt for {expense['Description']} is missing.")
