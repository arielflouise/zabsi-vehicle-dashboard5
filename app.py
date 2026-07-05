import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import datetime
import json
from google.oauth2.service_account import Credentials
import gspread

st.set_page_config(page_title="Zabsi Vehicle Control", page_icon="🛻", layout="wide")

st.title("📊 ZABSI Fleet, Booking & Compliance System")
st.markdown("Sistem Log Penggunaan Kenderaan dan Pemantauan Tarikh Dokumen Syarikat secara Live.")

# 1. Get credentials from Secrets
try:
    sheet_url = st.secrets["connections"]["gsheets"]["spreadsheet"]
    sheet_id = sheet_url.split("/d/")[1].split("/")[0]
    
    # Load service account info from individual secret keys
    service_account_info = {
        "type": st.secrets["google_service_account"]["type"],
        "project_id": st.secrets["google_service_account"]["project_id"],
        "private_key_id": st.secrets["google_service_account"]["private_key_id"],
        "private_key": st.secrets["google_service_account"]["private_key"],
        "client_email": st.secrets["google_service_account"]["client_email"],
        "client_id": st.secrets["google_service_account"]["client_id"],
        "auth_uri": st.secrets["google_service_account"]["auth_uri"],
        "token_uri": st.secrets["google_service_account"]["token_uri"],
        "auth_provider_x509_cert_url": st.secrets["google_service_account"]["auth_provider_x509_cert_url"],
        "client_x509_cert_url": st.secrets["google_service_account"]["client_x509_cert_url"],
        "universe_domain": st.secrets["google_service_account"]["universe_domain"]
    }
    
except Exception as e:
    st.error(f"Error loading credentials: {str(e)}")
    st.stop()

# 2. Connect to Google Sheets
try:
    credentials = Credentials.from_service_account_info(
        service_account_info,
        scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    
    # Connect to Google Sheets using streamlit-gsheets-connection
    conn = st.connection("gsheets", type=GSheetsConnection)
    df = conn.read(ttl=1)
    
    # Direct gspread client for write operations
    gc = gspread.authorize(credentials)
    spreadsheet = gc.open_by_key(sheet_id)
    worksheet = spreadsheet.get_worksheet(0)
    
except Exception as e:
    st.error(f"Failed to connect to Google Sheets: {str(e)}")
    st.stop()

# Clean Date Columns
for col in ["Tarikh Mula", "Tarikh Tamat", "Road Tax Expiry", "Insurance Expiry", "Puspakom Expiry"]:
    if col in df.columns:
        df[col] = pd.to_datetime(df[col], errors='coerce')

today = datetime.datetime.now()

# --- SIDEBAR: BOOKING FORM ---
st.sidebar.header("➕ Borang Tempahan Baru")

if not df.empty and "No. Pendaftaran" in df.columns:
    unique_vehicles = sorted(df["Kenderaan"].dropna().unique()) if "Kenderaan" in df.columns else []
    unique_plates = sorted(df["No. Pendaftaran"].dropna().unique())

    with st.sidebar.form(key="booking_form", clear_on_submit=True):
        input_vehicle = st.selectbox("Pilih Kenderaan", unique_vehicles) if unique_vehicles else st.text_input("Nama Kenderaan")
        input_plate = st.selectbox("No. Pendaftaran", unique_plates)

        matched_rows = df[df["No. Pendaftaran"] == input_plate]
        default_fuel = matched_rows["Jenis Minyak"].values[0] if "Jenis Minyak" in df.columns and not matched_rows.empty else "PETROL"
        st.caption(f"⛽ Jenis Minyak: **{default_fuel}**")

        input_start = st.date_input("Tarikh Mula Perjalanan", datetime.date.today())
        input_end = st.date_input("Tarikh Tamat Perjalanan", datetime.date.today())
        input_lokasi = st.text_input("📍 Lokasi / Site")
        input_pic = st.text_input("👤 Nama PIC / Pemandu")
        input_nota = st.text_input("📝 Nota / Kegunaan (Opsional)")

        submit_button = st.form_submit_button(label="Hantar Tempahan")

    if submit_button:
        if not input_lokasi or not input_pic:
            st.sidebar.error("❌ Sila isi bahagian Lokasi dan PIC!")
        else:
            # Get compliance details
            rt_val = matched_rows["Road Tax Expiry"].values[0] if "Road Tax Expiry" in df.columns and not matched_rows.empty else None
            ins_val = matched_rows["Insurance Expiry"].values[0] if "Insurance Expiry" in df.columns and not matched_rows.empty else None
            pk_val = matched_rows["Puspakom Expiry"].values[0] if "Puspakom Expiry" in df.columns and not matched_rows.empty else None

            rt_str = pd.to_datetime(rt_val).strftime('%Y-%m-%d') if pd.notnull(rt_val) else ""
            ins_str = pd.to_datetime(ins_val).strftime('%Y-%m-%d') if pd.notnull(ins_val) else ""
            pk_str = pd.to_datetime(pk_val).strftime('%Y-%m-%d') if pd.notnull(pk_val) else ""

            new_row_idx = len(df) + 1

            # Prepare new row data
            new_row_data = [
                new_row_idx,
                str(input_vehicle),
                str(input_plate),
                str(default_fuel),
                input_start.strftime('%Y-%m-%d'),
                input_end.strftime('%Y-%m-%d'),
                str(input_lokasi),
                str(input_pic),
                str(input_nota) if input_nota else "",
                rt_str,
                ins_str,
                pk_str
            ]

            try:
                worksheet.append_row(new_row_data)
                
                # Refresh data
                df = conn.read(ttl=1)
                
                st.sidebar.success("✅ Tempahan berjaya disimpan!")
                st.rerun()
                
            except Exception as e:
                st.sidebar.error(f"❌ Gagal menyimpan: {str(e)}")
                st.sidebar.info("Data yang cuba disimpan:")
                st.sidebar.json({
                    "No": new_row_idx,
                    "Kenderaan": str(input_vehicle),
                    "No. Pendaftaran": str(input_plate),
                    "Jenis Minyak": str(default_fuel),
                    "Tarikh Mula": input_start.strftime('%Y-%m-%d'),
                    "Tarikh Tamat": input_end.strftime('%Y-%m-%d'),
                    "Lokasi": str(input_lokasi),
                    "PIC": str(input_pic),
                    "Nota / Kegunaan": str(input_nota),
                    "Road Tax Expiry": rt_str,
                    "Insurance Expiry": ins_str,
                    "Puspakom Expiry": pk_str
                })
else:
    st.sidebar.warning("Sila pastikan data dalam Google Sheet anda diisi dengan betul.")

# --- MAIN DISPLAY ---
st.subheader("📋 Log Induk Fleet Kenderaan (Live dari Google Sheets)")
st.dataframe(df, use_container_width=True)

st.markdown("---")

# --- COMPLIANCE ALERTS ---
st.subheader("🚨 Amaran Pematuhan Dokumen")
if not df.empty and "No. Pendaftaran" in df.columns:
    cols_to_check = [c for c in ["Kenderaan", "No. Pendaftaran", "Road Tax Expiry", "Insurance Expiry", "Puspakom Expiry"] if c in df.columns]
    master_fleet = df[cols_to_check].drop_duplicates(subset=["No. Pendaftaran"])

    comp_col1, comp_col2, comp_col3 = st.columns(3)

    with comp_col1:
        st.markdown("#### 🚗 Road Tax Status")
        if "Road Tax Expiry" in master_fleet.columns:
            for _, row in master_fleet.iterrows():
                if pd.notnull(row["Road Tax Expiry"]):
                    days_left = (row["Road Tax Expiry"] - today).days
                    plate = row["No. Pendaftaran"]
                    if days_left < 0:
                        st.error(f"🔴 **{plate}** - EXPIRED ({abs(days_left)} days ago)")
                    elif days_left <= 30:
                        st.warning(f"🟡 **{plate}** - {days_left} days left!")
                    else:
                        st.success(f"🟢 **{plate}** - Active")

    with comp_col2:
        st.markdown("#### 🛡️ Insurance Status")
        if "Insurance Expiry" in master_fleet.columns:
            for _, row in master_fleet.iterrows():
                if pd.notnull(row["Insurance Expiry"]):
                    days_left = (row["Insurance Expiry"] - today).days
                    plate = row["No. Pendaftaran"]
                    if days_left < 0:
                        st.error(f"🔴 **{plate}** - EXPIRED!")
                    elif days_left <= 30:
                        st.warning(f"🟡 **{plate}** - {days_left} days left")
                    else:
                        st.success(f"🟢 **{plate}** - Covered")

    with comp_col3:
        st.markdown("#### 🚛 Puspakom Status")
        if "Puspakom Expiry" in master_fleet.columns:
            for _, row in master_fleet.iterrows():
                if pd.notnull(row["Puspakom Expiry"]):
                    days_left = (row["Puspakom Expiry"] - today).days
                    plate = row["No. Pendaftaran"]
                    if days_left < 0:
                        st.error(f"🔴 **{plate}** - OVERDUE")
                    elif days_left <= 30:
                        st.warning(f"🟡 **{plate}** - Due in {days_left} days")
                    else:
                        st.success(f"🟢 **{plate}** - Valid")
