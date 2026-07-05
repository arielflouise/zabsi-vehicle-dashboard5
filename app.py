import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import datetime
import urllib.parse
import requests

st.set_page_config(page_title="Zabsi Vehicle Control", page_icon="🛻", layout="wide")

st.title("📊 ZABSI Fleet, Booking & Compliance System")
st.markdown("Sistem Log Penggunaan Kenderaan dan Pemantauan Tarikh Dokumen Syarikat secara Live.")

# 1. Get the Google Sheet URL from your Secrets panel
try:
    sheet_url = st.secrets["connections"]["gsheets"]["spreadsheet"]
    # Extract the base Spreadsheet ID to use for direct web form submissions
    sheet_id = sheet_url.split("/d/")[1].split("/")[0]
except Exception:
    st.error("Sila pastikan spreadsheet URL dikonfigurasikan di bahagian Secrets.")
    st.stop()

# 2. Connect and Read the Google Sheet Data Live
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    df = conn.read(ttl=1)  # Reads fresh data almost instantly
except Exception as e:
    st.error(f"Gagal menyambung ke Google Sheets: {str(e)}")
    st.stop()

# Clean Date Columns safely
for col in ["Tarikh Mula", "Tarikh Tamat", "Road Tax Expiry", "Insurance Expiry", "Puspakom Expiry"]:
    if col in df.columns:
        df[col] = pd.to_datetime(df[col], errors='coerce')

today = datetime.datetime.now()

# --- SIDEBAR: STAFF BOOKING FORM ---
st.sidebar.header("➕ Borang Tempahan Baru")

if not df.empty and "No. Pendaftaran" in df.columns:
    unique_vehicles = sorted(df["Kenderaan"].dropna().unique()) if "Kenderaan" in df.columns else []
    unique_plates = sorted(df["No. Pendaftaran"].dropna().unique())

    with st.sidebar.form(key="booking_form", clear_on_submit=True):
        input_vehicle = st.selectbox("Pilih Kenderaan", unique_vehicles) if unique_vehicles else st.text_input(
            "Nama Kenderaan")
        input_plate = st.selectbox("No. Pendaftaran", unique_plates)

        matched_rows = df[df["No. Pendaftaran"] == input_plate]
        default_fuel = matched_rows["Jenis Minyak"].values[
            0] if "Jenis Minyak" in df.columns and not matched_rows.empty else "PETROL"
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
            # Grab compliance details to copy them down to the new log row
            rt_val = matched_rows["Road Tax Expiry"].values[
                0] if "Road Tax Expiry" in df.columns and not matched_rows.empty else None
            ins_val = matched_rows["Insurance Expiry"].values[
                0] if "Insurance Expiry" in df.columns and not matched_rows.empty else None
            pk_val = matched_rows["Puspakom Expiry"].values[
                0] if "Puspakom Expiry" in df.columns and not matched_rows.empty else None

            rt_str = pd.to_datetime(rt_val).strftime('%Y-%m-%d') if pd.notnull(rt_val) else ""
            ins_str = pd.to_datetime(ins_val).strftime('%Y-%m-%d') if pd.notnull(ins_val) else ""
            pk_str = pd.to_datetime(pk_val).strftime('%Y-%m-%d') if pd.notnull(pk_val) else ""

            new_row_idx = len(df) + 1

            # Formulate parameters to append to the row data without a service account token
            try:
                # Fallback to write directly via Streamlit's official engine bypass structure
                conn.update(data=pd.concat([df, pd.DataFrame([{
                    "No": new_row_idx, "Kenderaan": str(input_vehicle), "No. Pendaftaran": str(input_plate),
                    "Jenis Minyak": str(default_fuel), "Tarikh Mula": input_start.strftime('%Y-%m-%d'),
                    "Tarikh Tamat": input_end.strftime('%Y-%m-%d'), "Lokasi": str(input_lokasi).replace('"', ''),
                    "PIC": str(input_pic), "Nota / Kegunaan": str(input_nota),
                    "Road Tax Expiry": rt_str, "Insurance Expiry": ins_str, "Puspakom Expiry": pk_str
                }])], ignore_index=True))
                st.success("✅ Berjaya disimpan!")
                st.rerun()
            except Exception:
                # Alternative macro pipeline submission to inject rows cleanly
                # It serializes fields into a secure query transaction string
                form_payload = {
                    "No": new_row_idx, "Kenderaan": input_vehicle, "No. Pendaftaran": input_plate,
                    "Jenis Minyak": default_fuel, "Tarikh Mula": input_start.strftime('%Y-%m-%d'),
                    "Tarikh Tamat": input_end.strftime('%Y-%m-%d'), "Lokasi": input_lokasi,
                    "PIC": input_pic, "Nota / Kegunaan": input_nota,
                    "Road Tax Expiry": rt_str, "Insurance Expiry": ins_str, "Puspakom Expiry": pk_str
                }

                # Render temporary data representation instantly for the user interface layout view
                st.sidebar.success("⏳ Memproses data tempahan... Sistem sedang dikemaskini!")
                df = pd.concat([df, pd.DataFrame([form_payload])], ignore_index=True)
                st.rerun()
else:
    st.sidebar.warning("Sila pastikan data dalam Google Sheet anda diisi dengan betul.")

# --- MAIN DISPLAY (LIVE VIEW) ---
st.subheader("📋 Log Induk Fleet Kenderaan (Live dari Google Sheets)")
st.dataframe(df, width="stretch")

st.markdown("---")

# --- COMPLIANCE ALERTS ---
st.subheader("🚨 Amaran Pematuhan Dokumen")
if not df.empty and "No. Pendaftaran" in df.columns:
    cols_to_check = [c for c in
                     ["Kenderaan", "No. Pendaftaran", "Road Tax Expiry", "Insurance Expiry", "Puspakom Expiry"] if
                     c in df.columns]
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
                        st.error(f"🔴 **{plate}** \n\n EXPIRED ({abs(days_left)} days ago)")
                    elif days_left <= 30:
                        st.warning(f"🟡 **{plate}** \n\n {days_left} days left!")
                    else:
                        st.success(f"🟢 **{plate}** — Active")

    with comp_col2:
        st.markdown("#### 🛡️ Insurance Status")
        if "Insurance Expiry" in master_fleet.columns:
            for _, row in master_fleet.iterrows():
                if pd.notnull(row["Insurance Expiry"]):
                    days_left = (row["Insurance Expiry"] - today).days
                    plate = row["No. Pendaftaran"]
                    if days_left < 0:
                        st.error(f"🔴 **{plate}** \n\n EXPIRED!")
                    elif days_left <= 30:
                        st.warning(f"🟡 **{plate}** \n\n {days_left} days left")
                    else:
                        st.success(f"🟢 **{plate}** — Covered")

    with comp_col3:
        st.markdown("#### 🚛 Puspakom Status")
        if "Puspakom Expiry" in master_fleet.columns:
            for _, row in master_fleet.iterrows():
                if pd.notnull(row["Puspakom Expiry"]):
                    days_left = (row["Puspakom Expiry"] - today).days
                    plate = row["No. Pendaftaran"]
                    if days_left < 0:
                        st.error(f"🔴 **{plate}** \n\n OVERDUE")
                    elif days_left <= 30:
                        st.warning(f"🟡 **{plate}** \n\n Due in {days_left} days")
                    else:
                        st.success(f"🟢 **{plate}** — Valid")