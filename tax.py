import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore
import pyrebase
from datetime import datetime
import json

# Initialize Firebase Admin
@st.cache_resource
def init_firebase_admin():
    if not firebase_admin._apps:
        try:
            firebase_creds = json.loads(st.secrets["firebase_credentials"])
            cred = credentials.Certificate(firebase_creds)
            firebase_admin.initialize_app(cred)
        except Exception as e:
            st.error(f"Error initializing Firebase: {str(e)}")
    return firestore.client()

# Firebase Configuration
firebase_config = {
    "apiKey": st.secrets["firebase_config"]["api_key"],
    "authDomain": st.secrets["firebase_config"]["auth_domain"],
    "projectId": st.secrets["firebase_config"]["project_id"],
    "storageBucket": st.secrets["firebase_config"]["storage_bucket"],
    "messagingSenderId": st.secrets["firebase_config"]["messaging_sender_id"],
    "databaseURL": f"https://{st.secrets['firebase_config']['project_id']}.firebaseio.com"
}

# Initialize Pyrebase
firebase = pyrebase.initialize_app(firebase_config)
auth = firebase.auth()

def login_signup():
    st.title("Tax Expense Tracker")
    
    # Create tabs for Login and Sign Up
    tab1, tab2 = st.tabs(["Login", "Sign Up"])
    
    with tab1:  # Login
        email = st.text_input("Email", key="login_email")
        password = st.text_input("Password", type="password", key="login_password")
        
        if st.button("Login"):
            try:
                user = auth.sign_in_with_email_and_password(email, password)
                st.session_state['user'] = user
                st.success("Logged in successfully!")
                st.experimental_rerun()
            except Exception as e:
                st.error("Login failed. Please check your credentials.")
    
    with tab2:  # Sign Up
        email = st.text_input("Email", key="signup_email")
        password = st.text_input("Password", type="password", key="signup_password")
        confirm_password = st.text_input("Confirm Password", type="password")
        
        if st.button("Sign Up"):
            if password != confirm_password:
                st.error("Passwords do not match!")
                return
            
            try:
                user = auth.create_user_with_email_and_password(email, password)
                st.success("Account created successfully! Please login.")
                st.balloons()
            except Exception as e:
                st.error("Sign up failed. Please try again.")

def main():
    # Initialize Firebase
    db = init_firebase_admin()
    
    # Check authentication
    if 'user' not in st.session_state:
        login_signup()
        return

    # Main app UI
    st.title("Tax Expense Tracker")
    
    # Logout button
    if st.sidebar.button("Logout"):
        del st.session_state['user']
        st.experimental_rerun()

    # Add expense form
    with st.form("expense_form"):
        st.subheader("Add New Expense")
        col1, col2 = st.columns(2)
        
        with col1:
            expense_type = st.selectbox(
                "Expense Type",
                ["Transport", "Lunch", "Office Supplies", "Home Office", "Other"]
            )
            expense_description = st.text_input("Description")
        
        with col2:
            expense_amount = st.number_input("Amount (R)", min_value=0.0, format="%.2f")
            expense_date = st.date_input("Date")

        submitted = st.form_submit_button("Add Expense")
        if submitted:
            # Get user ID from session
            user_id = st.session_state.user['localId']
            
            # Create expense data
            expense_data = {
                "type": expense_type,
                "description": expense_description,
                "amount": expense_amount,
                "date": expense_date.strftime('%Y-%m-%d'),
                "timestamp": datetime.now()
            }
            
            # Save to Firestore
            db.collection('users').document(user_id).collection('expenses').add(expense_data)
            st.success("Expense added successfully!")
            st.experimental_rerun()

    # Display expenses
    user_id = st.session_state.user['localId']
    expenses_ref = db.collection('users').document(user_id).collection('expenses')
    expenses = []
    
    for doc in expenses_ref.stream():
        expense_data = doc.to_dict()
        expenses.append(expense_data)

    if expenses:
        import pandas as pd
        df = pd.DataFrame(expenses)
        
        # Calculate totals
        total = df['amount'].sum()
        st.metric("Total Expenses", f"R {total:,.2f}")
        
        # Display expense table
        st.dataframe(
            df[['date', 'type', 'description', 'amount']].sort_values('date', ascending=False),
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("No expenses recorded yet.")

if __name__ == "__main__":
    main()