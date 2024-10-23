import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore, auth
import pandas as pd
from datetime import datetime
import json
import bcrypt

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

def hash_password(password):
    """Hash password using bcrypt"""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt())

def check_password(password, hashed):
    """Verify password against hash"""
    return bcrypt.checkpw(password.encode(), hashed)

def login_signup():
    """Handle user authentication"""
    st.title("Tax Expense Tracker")
    
    # Create tabs for Login and Sign Up
    tab1, tab2 = st.tabs(["Login", "Sign Up"])
    
    with tab1:  # Login
        st.subheader("Login")
        email = st.text_input("Email", key="login_email")
        password = st.text_input("Password", type="password", key="login_password")
        
        if st.button("Login", key="login_button"):
            try:
                # Get user by email
                user = auth.get_user_by_email(email)
                # Get stored password hash from Firestore
                db = firestore.client()
                user_doc = db.collection('users').document(user.uid).get()
                if user_doc.exists:
                    stored_hash = user_doc.to_dict().get('password_hash')
                    if check_password(password, stored_hash):
                        st.session_state['user'] = {'localId': user.uid, 'email': email}
                        st.success("Successfully logged in!")
                        st.experimental_rerun()
                    else:
                        st.error("Invalid password")
                else:
                    st.error("User not found")
            except Exception as e:
                st.error("Login failed. Please check your credentials.")
    
    with tab2:  # Sign Up
        st.subheader("Create New Account")
        email = st.text_input("Email", key="signup_email")
        password = st.text_input("Password", type="password", key="signup_password")
        confirm_password = st.text_input("Confirm Password", type="password")
        
        if st.button("Sign Up", key="signup_button"):
            if password != confirm_password:
                st.error("Passwords do not match!")
                return
            
            try:
                # Create user in Firebase Auth
                user = auth.create_user(
                    email=email,
                    password=password
                )
                
                # Store additional user data in Firestore
                db = firestore.client()
                password_hash = hash_password(password)
                db.collection('users').document(user.uid).set({
                    'email': email,
                    'password_hash': password_hash,
                    'created_at': datetime.now()
                })
                
                st.success("Account created successfully! Please login.")
                st.balloons()
            except Exception as e:
                st.error(f"Sign up failed: {str(e)}")

def main():
    # Initialize Firebase
    db = init_firebase_admin()
    
    # Check if user is logged in
    if 'user' not in st.session_state:
        login_signup()
        return

    # Main app UI after login
    st.title("Tax Expense Tracker")
    
    # Add logout button to sidebar
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
            user_id = st.session_state.user['localId']
            expense_data = {
                "type": expense_type,
                "description": expense_description,
                "amount": expense_amount,
                "date": expense_date.strftime('%Y-%m-%d'),
                "timestamp": datetime.now()
            }
            
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
        df = pd.DataFrame(expenses)
        
        # Display metrics
        col1, col2, col3 = st.columns(3)
        total = df['amount'].sum()
        with col1:
            st.metric("Total Expenses", f"R {total:,.2f}")
        with col2:
            current_month = datetime.now().strftime('%Y-%m')
            monthly_total = df[df['date'].str.startswith(current_month)]['amount'].sum()
            st.metric("This Month", f"R {monthly_total:,.2f}")
        with col3:
            st.metric("Average Expense", f"R {total/len(expenses):,.2f}")
        
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