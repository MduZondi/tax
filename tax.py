import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore, auth
import pandas as pd
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

def add_expense(db, user_id, expense_data):
    """Add expense to Firestore and return success status"""
    try:
        db.collection('users').document(user_id).collection('expenses').add(expense_data)
        return True
    except Exception as e:
        st.error(f"Error adding expense: {str(e)}")
        return False

def main():
    # Initialize Firebase
    db = init_firebase_admin()
    
    # Check if user is logged in
    if 'user' not in st.session_state:
        # Your existing login code here...
        st.title("Tax Expense Tracker")
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Login"):
                try:
                    user = auth.get_user_by_email(email)
                    st.session_state['user'] = {'localId': user.uid, 'email': email}
                    st.success("Logged in successfully!")
                    st.rerun()
                except Exception as e:
                    st.error("Login failed")
        
        with col2:
            if st.button("Sign Up"):
                try:
                    user = auth.create_user(email=email, password=password)
                    st.success("Account created! Please login.")
                except Exception as e:
                    st.error(f"Sign up failed: {str(e)}")
        return

    # Main app UI after login
    st.title("Tax Expense Tracker")
    
    # Add logout button to sidebar
    if st.sidebar.button("Logout"):
        del st.session_state['user']
        st.rerun()

    # Add expense form
    with st.form("expense_form", clear_on_submit=True):
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
            
            if add_expense(db, user_id, expense_data):
                st.success("Expense added successfully!")
            else:
                st.error("Failed to add expense")

    # Display expenses
    st.subheader("Your Expenses")
    user_id = st.session_state.user['localId']
    expenses_ref = db.collection('users').document(user_id).collection('expenses')
    expenses = []
    
    for doc in expenses_ref.stream():
        expense_data = doc.to_dict()
        expenses.append(expense_data)

    if expenses:
        df = pd.DataFrame(expenses)
        total = df['amount'].sum()
        
        # Display metrics
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Expenses", f"R {total:,.2f}")
        with col2:
            current_month = datetime.now().strftime('%Y-%m')
            monthly_expenses = df[df['date'].str.startswith(current_month)] if 'date' in df else pd.DataFrame()
            monthly_total = monthly_expenses['amount'].sum() if not monthly_expenses.empty else 0
            st.metric("This Month", f"R {monthly_total:,.2f}")
        with col3:
            avg_expense = total / len(expenses) if expenses else 0
            st.metric("Average Expense", f"R {avg_expense:,.2f}")
        
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