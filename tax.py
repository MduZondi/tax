import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore, auth, storage
import pandas as pd
from datetime import datetime, timedelta
import plotly.express as px
import plotly.graph_objects as go
from fpdf import FPDF
import json
import uuid
from PIL import Image
import tempfile
import os
import io
import requests

# Initialize Firebase Admin
@st.cache_resource
def init_firebase_admin():
    if not firebase_admin._apps:
        try:
            firebase_creds = json.loads(st.secrets["firebase_credentials"])
            cred = credentials.Certificate(firebase_creds)
            firebase_admin.initialize_app(cred, {
                'storageBucket': f"{st.secrets['firebase_config']['project_id']}.appspot.com"
            })
        except Exception as e:
            st.error(f"Error initializing Firebase: {str(e)}")
    return firestore.client()

def calculate_tax_bracket(income):
    """Calculate tax bracket based on income"""
    tax_brackets = [
        (1, 237100, 0.18, 0),
        (237101, 370500, 0.26, 42678),
        (370501, 512800, 0.31, 77362),
        (512801, 673000, 0.36, 121475),
        (673001, 857900, 0.39, 179147),
        (857901, 1817000, 0.41, 251258),
        (1817001, float('inf'), 0.45, 644489)
    ]
    
    for min_income, max_income, rate, base_tax in tax_brackets:
        if min_income <= income <= max_income:
            tax = base_tax + (income - min_income + 1) * rate
            return tax, rate
    return 0, 0

def upload_receipt_to_firebase(user_id, receipt_file):
    """Upload receipt to Firebase Storage"""
    if receipt_file:
        try:
            bucket = storage.bucket()
            file_extension = os.path.splitext(receipt_file.name)[1]
            blob_name = f"receipts/{user_id}/{datetime.now().strftime('%Y%m%d_%H%M%S')}_{str(uuid.uuid4())}{file_extension}"
            blob = bucket.blob(blob_name)
            
            # Upload file
            blob.upload_from_string(
                receipt_file.getvalue(),
                content_type=receipt_file.type
            )
            
            # Make public and get URL
            blob.make_public()
            return blob.public_url
        except Exception as e:
            st.error(f"Error uploading receipt: {str(e)}")
            return None
    return None

def generate_detailed_pdf(user_data, expenses, tax_summary, filename='Tax_Report.pdf'):
    pdf = FPDF()
    
    # Cover Page
    pdf.add_page()
    pdf.set_font("Arial", 'B', size=24)
    pdf.cell(200, 40, txt="Tax Report & Analysis", ln=True, align='C')
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, txt=f"Generated on: {datetime.now().strftime('%Y-%m-%d')}", ln=True, align='C')
    pdf.cell(200, 10, txt=f"For Tax Year: {datetime.now().year}", ln=True, align='C')
    
    # Income Summary
    pdf.add_page()
    pdf.set_font("Arial", 'B', size=16)
    pdf.cell(200, 20, txt="Income Summary", ln=True)
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, txt=f"Gross Income: R{user_data.get('gross_income', 0):,.2f}", ln=True)
    pdf.cell(200, 10, txt=f"Tax Bracket: {tax_summary['tax_rate']*100}%", ln=True)
    pdf.cell(200, 10, txt=f"Estimated Tax: R{tax_summary['estimated_tax']:,.2f}", ln=True)
    
    # Deductions Summary
    pdf.add_page()
    pdf.set_font("Arial", 'B', size=16)
    pdf.cell(200, 20, txt="Deductions Summary", ln=True)
    pdf.set_font("Arial", size=12)
    for category, amount in tax_summary['deductions'].items():
        pdf.cell(200, 10, txt=f"{category}: R{amount:,.2f}", ln=True)
    
    # Expense Details
    pdf.add_page()
    pdf.set_font("Arial", 'B', size=16)
    pdf.cell(200, 20, txt="Detailed Expenses", ln=True)
    
    # Table header
    pdf.set_font("Arial", 'B', size=10)
    pdf.cell(40, 10, "Date", border=1)
    pdf.cell(40, 10, "Type", border=1)
    pdf.cell(70, 10, "Description", border=1)
    pdf.cell(40, 10, "Amount (R)", border=1)
    pdf.ln()
    
    # Table data
    pdf.set_font("Arial", size=10)
    for expense in expenses:
        pdf.cell(40, 10, expense["date"], border=1)
        pdf.cell(40, 10, expense["type"], border=1)
        pdf.cell(70, 10, expense["description"][:35], border=1)
        pdf.cell(40, 10, f"R{expense['amount']:,.2f}", border=1)
        pdf.ln()
    
    # Save to temporary file
    with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
        pdf.output(tmp.name)
        return tmp.name

def create_expense_charts(expenses_df):
    """Create various expense analysis charts"""
    # Monthly expenses trend
    monthly_expenses = expenses_df.groupby(pd.to_datetime(expenses_df['date']).dt.to_period('M'))['amount'].sum()
    fig_trend = px.line(
        x=monthly_expenses.index.astype(str),
        y=monthly_expenses.values,
        title='Monthly Expenses Trend',
        labels={'x': 'Month', 'y': 'Total Amount (R)'}
    )
    
    # Expense by category
    category_expenses = expenses_df.groupby('type')['amount'].sum()
    fig_pie = px.pie(
        values=category_expenses.values,
        names=category_expenses.index,
        title='Expenses by Category'
    )
    
    return fig_trend, fig_pie

def main():
    db = init_firebase_admin()
    
    # Authentication
    if 'user' not in st.session_state:
        st.title("Tax Expense Tracker - Login")
        
        tab1, tab2 = st.tabs(["Login", "Sign Up"])
        
        with tab1:
            email = st.text_input("Email", key="login_email")
            password = st.text_input("Password", type="password", key="login_password")
            
            if st.button("Login"):
                try:
                    user = auth.get_user_by_email(email)
                    st.session_state['user'] = {'localId': user.uid, 'email': email}
                    st.success("Logged in successfully!")
                    st.rerun()
                except Exception as e:
                    st.error("Login failed")
        
        with tab2:
            email = st.text_input("Email", key="signup_email")
            password = st.text_input("Password", type="password", key="signup_password")
            if st.button("Sign Up"):
                try:
                    user = auth.create_user(email=email, password=password)
                    st.success("Account created! Please login.")
                except Exception as e:
                    st.error(f"Sign up failed: {str(e)}")
        return

    # Main app UI
    st.title("Advanced Tax Expense Tracker")
    
    if st.sidebar.button("Logout"):
        del st.session_state['user']
        st.rerun()

    user_id = st.session_state.user['localId']
    user_ref = db.collection('users').document(user_id)

    # Navigation
    page = st.sidebar.radio("Navigate to", 
        ["Dashboard", "Income & Deductions", "Expenses", "Tax Calculator", "Reports"])

    if page == "Dashboard":
        st.header("Dashboard")
        
        # Load user data and expenses
        user_data = user_ref.get().to_dict() or {}
        expenses = list(user_ref.collection('expenses').stream())
        expenses_data = [doc.to_dict() for doc in expenses]
        
        if expenses_data:
            df = pd.DataFrame(expenses_data)
            
            # Display key metrics
            col1, col2, col3 = st.columns(3)
            with col1:
                total_expenses = df['amount'].sum()
                st.metric("Total Expenses", f"R {total_expenses:,.2f}")
            with col2:
                monthly_total = df[df['date'].str.startswith(datetime.now().strftime('%Y-%m'))]['amount'].sum()
                st.metric("This Month", f"R {monthly_total:,.2f}")
            with col3:
                avg_expense = total_expenses/len(expenses_data)
                st.metric("Average Expense", f"R {avg_expense:,.2f}")
            
            # Display charts
            fig_trend, fig_pie = create_expense_charts(df)
            st.plotly_chart(fig_trend)
            st.plotly_chart(fig_pie)

    elif page == "Income & Deductions":
        st.header("Income and Deductions")
        
        with st.form("income_form"):
            st.subheader("Income Details")
            gross_income = st.number_input("Annual Gross Income (R)", min_value=0.0, format="%.2f")
            retirement_contributions = st.number_input("Retirement Contributions (R)", min_value=0.0, format="%.2f")
            medical_aid_contributions = st.number_input("Medical Aid Contributions (R)", min_value=0.0, format="%.2f")
            
            st.subheader("Additional Deductions")
            work_from_home = st.number_input("Work from Home Expenses (R)", min_value=0.0, format="%.2f")
            professional_fees = st.number_input("Professional Body Fees (R)", min_value=0.0, format="%.2f")
            
            submitted = st.form_submit_button("Save Details")
            if submitted:
                data = {
                    'gross_income': gross_income,
                    'retirement_contributions': retirement_contributions,
                    'medical_aid_contributions': medical_aid_contributions,
                    'work_from_home': work_from_home,
                    'professional_fees': professional_fees,
                    'updated_at': datetime.now()
                }
                user_ref.set(data, merge=True)
                st.success("Details saved successfully!")

    elif page == "Expenses":
        st.header("Expense Management")
        
        with st.form("expense_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                expense_type = st.selectbox("Expense Type", 
                    ["Transport", "Home Office", "Professional Development", 
                     "Equipment", "Supplies", "Other"])
                expense_description = st.text_input("Description")
            
            with col2:
                expense_amount = st.number_input("Amount (R)", min_value=0.0, format="%.2f")
                expense_date = st.date_input("Date")
            
            receipt_file = st.file_uploader("Upload Receipt", type=["jpg", "jpeg", "png", "pdf"])
            
            submitted = st.form_submit_button("Add Expense")
            if submitted:
                receipt_url = upload_receipt_to_firebase(user_id, receipt_file)
                
                expense_data = {
                    "type": expense_type,
                    "description": expense_description,
                    "amount": expense_amount,
                    "date": expense_date.strftime('%Y-%m-%d'),
                    "receipt_url": receipt_url,
                    "timestamp": datetime.now()
                }
                
                user_ref.collection('expenses').add(expense_data)
                st.success("Expense added successfully!")

        # Display expenses
        expenses = list(user_ref.collection('expenses')
                       .order_by('date', direction=firestore.Query.DESCENDING)
                       .stream())
        
        if expenses:
            st.subheader("Recent Expenses")
            for doc in expenses:
                data = doc.to_dict()
                with st.expander(f"{data['date']} - {data['description']} (R{data['amount']:,.2f})"):
                    st.write(f"Type: {data['type']}")
                    st.write(f"Amount: R{data['amount']:,.2f}")
                    if data.get('receipt_url'):
                        st.image(data['receipt_url'], caption="Receipt")

    elif page == "Tax Calculator":
        st.header("Tax Calculator")
        
        # Load user data
        user_data = user_ref.get().to_dict() or {}
        gross_income = user_data.get('gross_income', 0)
        
        # Calculate tax
        tax_amount, tax_rate = calculate_tax_bracket(gross_income)
        
        # Calculate deductions
        total_deductions = (
            user_data.get('retirement_contributions', 0) +
            user_data.get('medical_aid_contributions', 0) +
            user_data.get('work_from_home', 0) +
            user_data.get('professional_fees', 0)
        )
        
        # Display calculations
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Gross Income", f"R {gross_income:,.2f}")
            st.metric("Tax Bracket", f"{tax_rate*100}%")
            st.metric("Estimated Tax", f"R {tax_amount:,.2f}")
        
        with col2:
            st.metric("Total Deductions", f"R {total_deductions:,.2f}")
            taxable_income = max(0, gross_income - total_deductions)
            st.metric("Taxable Income", f"R {taxable_income:,.2f}")
            final_tax = max(0, calculate_tax_bracket(taxable_income)[0])
            st.metric("Final Tax Amount", f"R {final_tax:,.2f}")

    elif page == "Reports":
        st.header("Reports and Analysis")
        
        report_type = st.selectbox("Select Report Type", 
            ["Tax Summary", "Expense Analysis", "Deductions Overview"])
        
            
        if report_type == "Tax Summary":
                # Generate comprehensive tax summary
                user_data = user_ref.get().to_dict() or {}
                expenses = list(user_ref.collection('expenses').stream())
                expenses_data = [doc.to_dict() for doc in expenses]
                
                tax_summary = {
                    'gross_income': user_data.get('gross_income', 0),
                    'tax_rate': calculate_tax_bracket(user_data.get('gross_income', 0))[1],
                    'estimated_tax': calculate_tax_bracket(user_data.get('gross_income', 0))[0],
                    'deductions': {
                        'Retirement': user_data.get('retirement_contributions', 0),
                        'Medical Aid': user_data.get('medical_aid_contributions', 0),
                        'Work from Home': user_data.get('work_from_home', 0),
                        'Professional Fees': user_data.get('professional_fees', 0),
                        'Other Expenses': sum(expense['amount'] for expense in expenses_data)
                    }
                }
                
                # Display summary
                st.subheader("Tax Summary Report")
                st.write(f"**Tax Year:** {datetime.now().year}")
                st.write(f"**Gross Income:** R{tax_summary['gross_income']:,.2f}")
                st.write(f"**Tax Bracket:** {tax_summary['tax_rate']*100}%")
                st.write(f"**Estimated Tax:** R{tax_summary['estimated_tax']:,.2f}")
                
                # Display deductions breakdown
                st.subheader("Deductions Breakdown")
                fig = go.Figure([go.Bar(
                    x=list(tax_summary['deductions'].keys()),
                    y=list(tax_summary['deductions'].values())
                )])
                fig.update_layout(title="Deductions by Category")
                st.plotly_chart(fig)
                
                # Generate PDF Report
                if st.button("Generate PDF Report"):
                    pdf_path = generate_detailed_pdf(user_data, expenses_data, tax_summary)
                    with open(pdf_path, "rb") as pdf_file:
                        st.download_button(
                            "Download Tax Summary Report",
                            pdf_file,
                            file_name=f"Tax_Summary_{datetime.now().strftime('%Y%m%d')}.pdf",
                            mime="application/pdf"
                        )
                    os.unlink(pdf_path)

        elif report_type == "Expense Analysis":
                st.subheader("Expense Analysis")
                
                # Load expenses
                expenses = list(user_ref.collection('expenses').stream())
                expenses_data = [doc.to_dict() for doc in expenses]
                
                if expenses_data:
                    df = pd.DataFrame(expenses_data)
                    df['date'] = pd.to_datetime(df['date'])
                    
                    # Time period selection
                    period = st.selectbox("Select Time Period", 
                        ["Last Month", "Last 3 Months", "Last 6 Months", "This Year", "All Time"])
                    
                    # Filter data based on selected period
                    today = datetime.now()
                    if period == "Last Month":
                        start_date = today - timedelta(days=30)
                    elif period == "Last 3 Months":
                        start_date = today - timedelta(days=90)
                    elif period == "Last 6 Months":
                        start_date = today - timedelta(days=180)
                    elif period == "This Year":
                        start_date = datetime(today.year, 1, 1)
                    else:
                        start_date = df['date'].min()
                    
                    filtered_df = df[df['date'] >= start_date]
                    
                    # Display metrics
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Total Expenses", f"R {filtered_df['amount'].sum():,.2f}")
                    with col2:
                        st.metric("Average Monthly", f"R {filtered_df.groupby(filtered_df['date'].dt.to_period('M'))['amount'].sum().mean():,.2f}")
                    with col3:
                        st.metric("Number of Expenses", len(filtered_df))
                    
                    # Trend Analysis
                    st.subheader("Expense Trends")
                    monthly_trend = filtered_df.groupby(filtered_df['date'].dt.to_period('M'))['amount'].sum()
                    fig = px.line(x=monthly_trend.index.astype(str), y=monthly_trend.values,
                                title="Monthly Expense Trend",
                                labels={'x': 'Month', 'y': 'Amount (R)'})
                    st.plotly_chart(fig)
                    
                    # Category Analysis
                    st.subheader("Expense Categories")
                    category_totals = filtered_df.groupby('type')['amount'].sum()
                    fig = px.pie(values=category_totals.values, names=category_totals.index,
                               title="Expenses by Category")
                    st.plotly_chart(fig)
                    
                    # Detailed Breakdown Table
                    st.subheader("Detailed Breakdown")
                    breakdown_df = filtered_df.groupby('type').agg({
                        'amount': ['sum', 'mean', 'count']
                    }).round(2)
                    breakdown_df.columns = ['Total', 'Average', 'Count']
                    st.dataframe(breakdown_df)
                    
                else:
                    st.info("No expenses recorded yet.")    

        elif report_type == "Deductions Overview":
                st.subheader("Deductions Overview")
                
                # Load user data and expenses
                user_data = user_ref.get().to_dict() or {}
                expenses = list(user_ref.collection('expenses').stream())
                expenses_data = [doc.to_dict() for doc in expenses]
                
                # Calculate all possible deductions
                retirement_limit = min(
                    user_data.get('retirement_contributions', 0),
                    user_data.get('gross_income', 0) * 0.275,  # 27.5% limit
                    350000  # Annual limit
                )
                
                medical_credit = user_data.get('medical_aid_contributions', 0) * 12 * 0.25  # 25% medical credit
                
                # Create deductions summary
                deductions_summary = {
                    'Retirement Contributions': retirement_limit,
                    'Medical Aid Credits': medical_credit,
                    'Work from Home': user_data.get('work_from_home', 0),
                    'Professional Fees': user_data.get('professional_fees', 0),
                    'Travel Expenses': sum(e['amount'] for e in expenses_data if e['type'] == 'Transport'),
                    'Home Office Expenses': sum(e['amount'] for e in expenses_data if e['type'] == 'Home Office')
                }
                
                # Display summary
                for category, amount in deductions_summary.items():
                    st.metric(category, f"R {amount:,.2f}")
                
                # Visualization
                fig = go.Figure(data=[
                    go.Bar(name='Amount',
                          x=list(deductions_summary.keys()),
                          y=list(deductions_summary.values()))
                ])
                fig.update_layout(title="Deductions Overview")
                st.plotly_chart(fig)
                
                # Recommendations
                st.subheader("Optimization Recommendations")
                if user_data.get('retirement_contributions', 0) < user_data.get('gross_income', 0) * 0.275:
                    st.info("💡 You can increase your retirement contributions to maximize tax benefits.")
                
                if not any(e['type'] == 'Home Office' for e in expenses_data):
                    st.info("💡 Consider claiming home office expenses if you work from home.")
                
                # Export Options
                if st.button("Export Deductions Report"):
                    # Generate detailed PDF report
                    pdf_path = generate_detailed_pdf(user_data, expenses_data, deductions_summary)
                    with open(pdf_path, "rb") as pdf_file:
                        st.download_button(
                            "Download Deductions Report",
                            pdf_file,
                            file_name=f"Deductions_Report_{datetime.now().strftime('%Y%m%d')}.pdf",
                            mime="application/pdf"
                        )
                    os.unlink(pdf_path)    

if __name__ == "__main__":
    main()    