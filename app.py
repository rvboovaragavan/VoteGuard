import streamlit as st
import pandas as pd
from rapidfuzz import process, fuzz
import plotly.express as px
import datetime
import base64
import os
import serial
from serial.tools import list_ports

def get_available_serial_ports():
    try:
        return [port.device for port in list_ports.comports()]
    except Exception:
        return []


def read_nfc_uid(port="COM10", baud=115200):
    try:
        with serial.Serial(port, baud, timeout=3) as ser:
            line = ser.readline().decode(errors="ignore").strip()
            if not line:
                return None, "No UID received from the ESP32. Verify the card is present and the device is sending data."
            return line, None
    except serial.SerialException as exc:
        return None, f"Serial error: {exc}"
    except Exception as exc:
        return None, f"Failed to open serial port: {exc}"
# ==========================================
# PAGE CONFIGURATION
# ==========================================
st.set_page_config(page_title="VoteGuard Dashboard", page_icon="🛡️", layout="wide")

def set_background(image_path):
    """Sets a background image for the main application area."""
    if os.path.exists(image_path):
        with open(image_path, "rb") as img_file:
            encoded_string = base64.b64encode(img_file.read()).decode()
            
        ext = image_path.split('.')[-1].lower()
        mime_type = f"image/{ext}" if ext != "jpg" else "image/jpeg"
        
        st.markdown(
            f"""
            <style>
            .stApp {{
                background-image: url(data:{mime_type};base64,{encoded_string});
                background-size: cover;
                background-attachment: fixed;
                background-position: center;
            }}
            
            /* Make background slightly dark transparent over the image for better readability */
            .stApp > header {{
                background-color: transparent;
            }}
            .block-container {{
                background-color: rgba(14, 17, 23, 0.85); /* Semi-transparent dark overlay */
                border-radius: 15px;
                padding: 2rem;
                margin-top: 1rem;
            }}
            </style>
            """,
            unsafe_allow_html=True
        )

# ==========================================
# STATE MANAGEMENT
# ==========================================
def initialize_state():
    """Initializes Streamlit session state variables for state persistence."""
    if 'audit_logs' not in st.session_state:
        st.session_state.audit_logs = []
    if 'processed_df' not in st.session_state:
        st.session_state.processed_df = None
    if 'voted_ids' not in st.session_state:
        st.session_state.voted_ids = []

def add_audit_log(message):
    """Appends an event message to the audit logs."""
    st.session_state.audit_logs.append({
        "Timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "Event": message
    })

# ==========================================
# DATA PROCESSING ENGINE (EXPLAINABLE AI)
# ==========================================
def process_data(df):
    """
    Validates the dataset, applies risk logic, and enriches data.
    Returns: (processed_dataframe, error_message_if_any)
    """
    df = df.copy()
    df = df.reset_index(drop=True)
    
    # 1. Validate Schema
    required_cols = {'VoterID', 'Name', 'Age', 'City', 'State', 'PartialID', 'LastUpdated'}
    if not required_cols.issubset(set(df.columns)):
        missing = required_cols - set(df.columns)
        return None, f"Missing required columns: {', '.join(missing)}"

    # 2. Prepare Data
    risk_levels = []
    reasons_list = []
    scores = []
    
    # Pre-compute frequencies and lists to optimize the loop
    partial_id_counts = df['PartialID'].dropna().value_counts()
    names_list = df['Name'].fillna("").astype(str).tolist()
    
    # 3. Apply Risk Rules
    for idx, row in df.iterrows():
        score = 0
        reasons = []
        
        # Rule 1: Duplicate PartialID -> +3
        pid = row['PartialID']
        if pd.notna(pid) and partial_id_counts.get(pid, 0) > 1:
            score += 3
            reasons.append("Duplicate PartialID")
            
        # Rule 2: LastUpdated < 2015 -> +2
        try:
            if pd.notna(row['LastUpdated']):
                last_updated = int(float(row['LastUpdated']))
                if last_updated < 2015:
                    score += 2
                    reasons.append("LastUpdated < 2015")
        except (ValueError, TypeError):
            pass
            
        # Rule 3: Age > 100 -> +3
        try:
            if pd.notna(row['Age']):
                age = int(float(row['Age']))
                if age > 100:
                    score += 3
                    reasons.append("Age > 100")
        except (ValueError, TypeError):
            pass
            
        # Rule 4: Name similarity using RapidFuzz -> +2
        name = str(row['Name']).strip() if pd.notna(row['Name']) else ""
        if name:
            # Check similarity against all other names (limit=2 to capture self + 1 other)
            matches = process.extract(name, names_list, scorer=fuzz.ratio, limit=2)
            has_similar = False
            for match_tuple in matches:
                # Expected match tuple from rapidfuzz: (string, score, index)
                if len(match_tuple) >= 3:
                    m_str, m_score, m_idx = match_tuple[:3]
                    # Check if there is a highly similar name at a different index
                    if m_idx != idx and m_score > 85:
                        has_similar = True
                        break
            if has_similar:
                score += 2
                reasons.append("Similar Name Found (>85% Match)")
                
        # 4. Risk Classification based on Score
        scores.append(score)
        if score >= 6:
            risk_levels.append("High Risk")
        elif score >= 3:
            risk_levels.append("Medium Risk")
        else:
            risk_levels.append("Low Risk")
            
        # Concatenate explanations
        reasons_list.append(" | ".join(reasons) if reasons else "None")
        
    # 5. Enrich Dataset
    df['Risk Score'] = scores
    df['Risk Level'] = risk_levels
    df['Reason'] = reasons_list
    
    return df, "Success"

# ==========================================
# MAIN APPLICATION
# ==========================================
def main():
    initialize_state()
    
    # Try multiple common extensions for the background image
    for img_name in ["background.png", "background.jpg", "background.jpeg"]:
        if os.path.exists(img_name):
            set_background(img_name)
            break

    # --- Header & Ethical Disclaimer ---
    st.title("VoteGuard – Smart Voter Verification System")
    st.info("⚠️ **Disclaimer:** This system supports human review only and does not make automated decisions.")

    # --- Data Input (Main Area) ---
    st.header("📂 Data Input")
    uploaded_file = st.file_uploader("Upload Voter Dataset (CSV)", type=["csv"])
    
    if not uploaded_file:
        st.info("💡 **Tip:** Dataset must include:\n`VoterID, Name, Age, City, State, PartialID, LastUpdated`")

    # --- Sidebar Configuration ---
    with st.sidebar:
        st.header("⚙️ System Status")
        st.success("Online & Secure")
        
        st.divider()
        
        st.header("📖 How to Use")
        st.markdown("""
        1. **Upload Data**: Use the Data Input area in the center to upload your CSV.
        2. **Review Analytics**: Check the *Analytics Dashboard* to see risk distribution.
        3. **Filter Records**: Use *Records Management* to find and export specific anomalies.
        4. **Track Logs**: View the *Audit Log* to trace automated system actions.
        5. **NFC Verification**: Use the *NFC Verification* tab to scan RFID cards for voter verification.
        """)
        
        st.divider()
        
        st.header("📊 Risk Levels Guide")
        st.markdown("""
        - 🔴 **High Risk**: Score ≥ 6
        - 🟠 **Medium Risk**: Score 3 - 5
        - 🟢 **Low Risk**: Score < 3
        """)
        
        st.divider()
        
        st.header("🔍 Detection Rules")
        st.info("""
        **Scoring System:**
        - **Duplicate PartialID**: +3 points
        - **Age > 100 Years**: +3 points
        - **Last Updated < 2015**: +2 points
        - **Fuzzy Name Match (>85%)**: +2 points
        """)
    if uploaded_file is not None:
        try:
            raw_df = pd.read_csv(uploaded_file)
            
            with st.spinner("Analyzing data and detecting risks using Explainable Rules..."):
                processed_df, msg = process_data(raw_df)
                
            if processed_df is not None:
                # Log upload if this is a new dataset
                if st.session_state.processed_df is None or len(st.session_state.processed_df) != len(processed_df):
                    st.session_state.processed_df = processed_df
                    
                    add_audit_log(f"File uploaded: {uploaded_file.name}. Total records processed: {len(processed_df)}.")
                    
                    high_cnt = (processed_df['Risk Level'] == 'High Risk').sum()
                    med_cnt = (processed_df['Risk Level'] == 'Medium Risk').sum()
                    low_cnt = (processed_df['Risk Level'] == 'Low Risk').sum()
                    add_audit_log(f"Risk Distribution - High: {high_cnt}, Medium: {med_cnt}, Low: {low_cnt}")
                    
                df = st.session_state.processed_df
                
                # --- Tab-Based Dashboard Navigation ---
                tab_analytics, tab_records, tab_audit, tab_nfc = st.tabs([
                    "📊 Analytics Dashboard", 
                    "📁 Records Management", 
                    "📜 Audit Log",
                    "🆔 NFC Verification"
                ])
                
                # ----------------------------------------
                # TAB 1: ANALYTICS DASHBOARD
                # ----------------------------------------
                with tab_analytics:
                    st.header("Analytics Dashboard")
                    
                    # KPIs
                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("Total Records", len(df))
                    c2.metric("High Risk", len(df[df['Risk Level'] == 'High Risk']))
                    c3.metric("Medium Risk", len(df[df['Risk Level'] == 'Medium Risk']))
                    c4.metric("Low Risk", len(df[df['Risk Level'] == 'Low Risk']))
                    
                    st.divider()
                    
                    # Visualizations - Row 1
                    col_bar, col_pie = st.columns(2)
                    color_map = {"High Risk": "#ef4444", "Medium Risk": "#f59e0b", "Low Risk": "#10b981"}
                    cat_order = {"Risk Level": ["High Risk", "Medium Risk", "Low Risk"]}
                    
                    with col_bar:
                        fig_bar = px.histogram(df, x="Risk Level", color="Risk Level", 
                                               color_discrete_map=color_map,
                                               title="Risk Distribution",
                                               category_orders=cat_order)
                        st.plotly_chart(fig_bar, use_container_width=True)
                        
                    with col_pie:
                        fig_pie = px.pie(df, names="Risk Level", title="Risk Proportion",
                                         color="Risk Level", 
                                         color_discrete_map=color_map,
                                         category_orders=cat_order)
                        st.plotly_chart(fig_pie, use_container_width=True)
                        
                    # Visualizations - Row 2
                    col_city, col_state = st.columns(2)
                    with col_city:
                        city_counts = df['City'].value_counts().reset_index()
                        city_counts.columns = ['City', 'Count']
                        fig_city = px.bar(city_counts.head(10), x='City', y='Count', 
                                          title="Top 10 Cities by Voter Count", 
                                          color_discrete_sequence=['#3b82f6'])
                        st.plotly_chart(fig_city, use_container_width=True)
                        
                    with col_state:
                        state_counts = df['State'].value_counts().reset_index()
                        state_counts.columns = ['State', 'Count']
                        fig_state = px.bar(state_counts.head(10), x='State', y='Count', 
                                           title="Top 10 States by Voter Count", 
                                           color_discrete_sequence=['#8b5cf6'])
                        st.plotly_chart(fig_state, use_container_width=True)

                # ----------------------------------------
                # TAB 2: RECORDS MANAGEMENT
                # ----------------------------------------
                with tab_records:
                    st.header("Records Management")
                    
                    # Filters Configuration
                    f1, f2, f3 = st.columns(3)
                    risk_filter = f1.multiselect("Filter by Risk Level", options=["High Risk", "Medium Risk", "Low Risk"])
                    city_filter = f2.multiselect("Filter by City", options=df['City'].dropna().unique())
                    state_filter = f3.multiselect("Filter by State", options=df['State'].dropna().unique())
                    
                    # Apply Filters
                    filtered_df = df.copy()
                    if risk_filter:
                        filtered_df = filtered_df[filtered_df['Risk Level'].isin(risk_filter)]
                    if city_filter:
                        filtered_df = filtered_df[filtered_df['City'].isin(city_filter)]
                    if state_filter:
                        filtered_df = filtered_df[filtered_df['State'].isin(state_filter)]
                        
                    # Display Filtered Data
                    display_cols = ['VoterID', 'Name', 'Age', 'City', 'State', 'Risk Score', 'Risk Level', 'Reason']
                    st.dataframe(filtered_df[display_cols], use_container_width=True)
                    
                    # CSV Export
                    csv_data = filtered_df.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="📥 Download Filtered Results (CSV)",
                        data=csv_data,
                        file_name='voteguard_filtered.csv',
                        mime='text/csv',
                    )

                # ----------------------------------------
                # TAB 3: AUDIT LOG
                # ----------------------------------------
                with tab_audit:
                    st.header("Audit Log")
                    st.write("System events and metrics logged for transparency.")
                    if st.session_state.audit_logs:
                        logs_df = pd.DataFrame(st.session_state.audit_logs)
                        st.dataframe(logs_df, use_container_width=True)
                    else:
                        st.info("No audit logs available.")
                        
                # ----------------------------------------
                # TAB 4: NFC VERIFICATION
                # ----------------------------------------
                with tab_nfc:
                    st.header("NFC Verification")
                    st.write("Scan RFID/NFC card to verify voter eligibility.")
                    
                    if st.session_state.processed_df is None:
                        st.warning("Please upload a voter dataset first.")
                    else:
                        df = st.session_state.processed_df
                        available_ports = get_available_serial_ports()
                        default_port = available_ports[0] if available_ports else "COM10"
                        port_choice = st.selectbox("Serial Port", options=available_ports or ["COM10"], index=0)
                        baud_choice = st.selectbox("Baud Rate", options=[115200, 57600, 9600], index=0)

                        if not available_ports:
                            st.warning("No serial ports detected. Confirm the ESP32 is connected and COM10 is available.")

                        if st.button("Scan NFC Card"):
                            with st.spinner("Scanning NFC card..."):
                                uid, error = read_nfc_uid(port=port_choice, baud=baud_choice)

                            if uid:
                                st.success(f"Scanned UID: {uid}")
                                
                                uid = uid.strip().upper()
                                df["RFID_UID"] = df["RFID_UID"].astype(str).str.strip().str.upper()
                                voter = df[df["RFID_UID"] == uid]
                                if not voter.empty:
                                    voter = voter.iloc[0]
                                    
                                    st.subheader("Voter Details")
                                    st.write(f"**Voter ID:** {voter['VoterID']}")
                                    st.write(f"**Name:** {voter['Name']}")
                                    st.write(f"**Age:** {voter['Age']}")
                                    st.write(f"**City:** {voter['City']}")
                                    st.write(f"**State:** {voter['State']}")
                                    st.write(f"**Risk Level:** {voter['Risk Level']}")
                                    
                                    if voter['VoterID'] in st.session_state.voted_ids:
                                        st.error("❌ Already Voted - Vote Blocked")
                                        add_audit_log(f"Voter {voter['VoterID']} attempted to vote again (blocked).")
                                    else:
                                        st.success("✅ Verified - Allow Vote")
                                        st.session_state.voted_ids.append(voter['VoterID'])
                                        add_audit_log(f"Voter {voter['VoterID']} verified and allowed to vote via NFC.")
                                else:
                                    st.warning("⚠️ UID not found in voter database. Manual verification required.")
                                    add_audit_log(f"Unknown UID {uid} scanned - manual verification required.")
                            else:
                                st.error(error or "Failed to read UID from ESP32. Check connection and try again.")
                        
                        # ----------------------------------------
                        # VOTING STATISTICS & RECORDS
                        # ----------------------------------------
                        st.divider()
                        st.subheader("📊 Voting Records")
                        
                        voted_count = len(st.session_state.voted_ids)
                        total_voters = len(df)
                        remaining_voters = total_voters - voted_count
                        
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("Total Voters", total_voters)
                        with col2:
                            st.metric("Voted", voted_count)
                        with col3:
                            st.metric("Remaining", remaining_voters)
                        
                        if voted_count > 0:
                            st.write("**Voters Who Have Voted:**")
                            voted_records = df[df['VoterID'].isin(st.session_state.voted_ids)][['VoterID', 'Name', 'City', 'State', 'Risk Level']]
                            st.dataframe(voted_records, use_container_width=True)
                            
                            # Download button
                            csv_data = voted_records.to_csv(index=False)
                            st.download_button(
                                label="📥 Download Voted Records (CSV)",
                                data=csv_data,
                                file_name="voted_records.csv",
                                mime="text/csv"
                            )
                        else:
                            st.info("No voters have scanned their cards yet.")

            else:
                st.sidebar.error(msg)
                
        except Exception as e:
            st.error(f"Error reading file. Ensure it is a valid CSV. Details: {e}")
    else:
        # Landing view when no data is uploaded
        st.markdown("### Welcome to VoteGuard!")
        st.write("Please **upload a Voter Dataset (CSV)** from the sidebar to begin.")
        st.write("**Expected Schema:**")
        st.code("VoterID, Name, Age, City, State, PartialID, LastUpdated")

if __name__ == "__main__":
    main()