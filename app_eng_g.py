import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import time

# --- Google Sheets Setup ---
SHEET_NAME = "Tivo_Inventory_DB"

def get_connection():
    """連線到 Google Sheets"""
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    return client

def get_worksheet(sheet_name):
    """取得特定的分頁 (Worksheet)"""
    client = get_connection()
    sh = client.open(SHEET_NAME)
    return sh.worksheet(sheet_name)

# --- CRUD Operations ---

def get_options(sheet_name):
    try:
        ws = get_worksheet(sheet_name)
        values = ws.col_values(1)
        return values[1:] if len(values) > 1 else []
    except Exception:
        return []

def add_new_option(sheet_name, value):
    ws = get_worksheet(sheet_name)
    existing = ws.col_values(1)
    if value in existing:
        return False
    ws.append_row([value])
    return True

def get_all_data():
    ws = get_worksheet("items")
    data = ws.get_all_records()
    df = pd.DataFrame(data)
    
    if not df.empty and 'date' in df.columns:
        df['date'] = pd.to_datetime(df['date'], errors='coerce').dt.date
    
    if not df.empty and 'id' in df.columns:
         df['id'] = pd.to_numeric(df['id'], errors='coerce')

    return df

# [修改] 增加 note 參數
def add_data(date, item_name, item_id, keeper, chip_code, location, note):
    ws = get_worksheet("items")
    new_id = int(datetime.now().timestamp())
    date_str = date.strftime("%Y-%m-%d")
    # [修改] 寫入時包含 note
    ws.append_row([new_id, date_str, item_name, item_id, keeper, chip_code, location, note])

# [修改] 增加 note 參數
def update_data(target_id, date, item_name, item_id, keeper, chip_code, location, note):
    ws = get_worksheet("items")
    cell = ws.find(str(target_id), in_column=1)
    
    if cell:
        row_num = cell.row
        date_str = date.strftime("%Y-%m-%d") if hasattr(date, 'strftime') else str(date)
        # [修改] 更新範圍改成 B:H (包含 Note 欄位)
        ws.update(f"B{row_num}:H{row_num}", [[date_str, item_name, item_id, keeper, chip_code, location, note]])

def delete_data(target_id):
    ws = get_worksheet("items")
    cell = ws.find(str(target_id), in_column=1)
    if cell:
        ws.delete_rows(cell.row)

# --- UI ---

def main():
    st.set_page_config(page_title="Tivo DK Inventory (Cloud)", layout="wide")
    
    # --- CSS 隱藏樣式 ---
    hide_st_style = """
        <style>
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;}
        </style>
        """
    st.markdown(hide_st_style, unsafe_allow_html=True)
    
    st.title("☁️ Tivo Development Kit Inventory System")
    st.caption("Data is synced directly to Google Sheets.")
    st.markdown("---")

    if 'chip_options' not in st.session_state:
        st.session_state.chip_options = get_options('chips')
    if 'location_options' not in st.session_state:
        st.session_state.location_options = get_options('locations')

    # --- Sidebar ---
    with st.sidebar:
        st.header("📝 Add New Asset")
        
        input_date = st.date_input("Date", datetime.now())
        input_name = st.text_input("Item Name", placeholder="e.g., Tivo Stream 4K")
        
        col_prefix, col_num = st.columns([1, 2])
        with col_prefix:
            # 依據你的截圖，這裡前綴是 VDEV-
            st.text_input("Prefix", "VDEV-", disabled=True)
        with col_num:
            input_id_num = st.text_input("ID Number", placeholder="e.g., 1001")
        
        input_keeper = st.text_input("Keeper", placeholder="e.g., John Doe")
        input_chip = st.selectbox("Chip Code", st.session_state.chip_options)
        input_loc = st.selectbox("Location", st.session_state.location_options)
        
        # [新增] Note 輸入框 (使用 text_area 可以輸入多行)
        input_note = st.text_area("Note", placeholder="Any remarks...", height=100)

        if st.button("Submit", type="primary"):
            if input_name and input_id_num:
                with st.spinner("Saving to Google Sheets..."):
                    full_id = f"VDEV-{input_id_num}"
                    # [修改] 傳入 input_note
                    add_data(input_date, input_name, full_id, input_keeper, input_chip, input_loc, input_note)
                    st.success(f"Added: {full_id}")
                    time.sleep(1)
                    st.rerun()
            else:
                st.error("Required fields missing!")

        st.markdown("---")
        with st.expander("⚙️ Manage Options"):
            new_chip = st.text_input("New Chip Code")
            if st.button("Add Chip"):
                if new_chip:
                    with st.spinner("Adding..."):
                        if add_new_option('chips', new_chip):
                            st.session_state.chip_options = get_options('chips')
                            st.success("Added!")
                            st.rerun()
                        else:
                            st.warning("Exists.")
            
            new_loc = st.text_input("New Location")
            if st.button("Add Location"):
                if new_loc:
                     with st.spinner("Adding..."):
                        if add_new_option('locations', new_loc):
                            st.session_state.location_options = get_options('locations')
                            st.success("Added!")
                            st.rerun()
                        else:
                            st.warning("Exists.")

    # --- Main List ---
    st.header("📋 Asset List")
    
    try:
        df = get_all_data()
    except Exception as e:
        st.error(f"Error connecting to Google Sheets: {e}")
        st.stop()

    if not df.empty:
        search_term = st.text_input("🔍 Search...", "")
        if search_term:
            mask = df.astype(str).apply(lambda x: x.str.contains(search_term, case=False)).any(axis=1)
            df = df[mask]

        df.insert(0, "Delete?", False)

        edited_df = st.data_editor(
            df,
            column_config={
                "Delete?": st.column_config.CheckboxColumn("Delete?", default=False),
                "id": None, # 保持隱藏 System ID
                "date": st.column_config.DateColumn("Date"),
                "item_name": st.column_config.TextColumn("Item Name"),
                "item_id": st.column_config.TextColumn("Full ID"),
                "keeper": st.column_config.TextColumn("Keeper"),
                "chip_code": st.column_config.SelectboxColumn("Chip", options=st.session_state.chip_options, required=True),
                "location": st.column_config.SelectboxColumn("Loc", options=st.session_state.location_options, required=True),
                # [新增] Note 欄位設定
                "note": st.column_config.TextColumn("Note", width="large")
            },
            hide_index=True,
            use_container_width=True
        )

        col_btn, col_info = st.columns([1, 4])
        with col_btn:
            if st.button("💾 Save Changes", type="primary"):
                try:
                    with st.spinner("Syncing to Google Sheets..."):
                        for index, row in edited_df.iterrows():
                            row_id = row['id']
                            if row['Delete?']:
                                delete_data(row_id)
                            else:
                                # [新增] 讀取 note 資料，如果是空的(NaN)則轉為空字串
                                note_val = str(row['note']) if pd.notna(row.get('note')) else ""
                                
                                update_data(
                                    row_id, row['date'], row['item_name'], 
                                    row['item_id'], row['keeper'], 
                                    row['chip_code'], row['location'],
                                    note_val # 傳入 Note
                                )
                    st.toast("✅ Google Sheets Updated!")
                    time.sleep(1)
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")

        # --- Export ---
        st.markdown("### 📥 Export")
        export_df = df.drop(columns=['Delete?', 'id'])
        # [修改] 匯出時包含 Note
        export_df = export_df.rename(columns={
            'date': 'Date',
            'item_name': 'Item Name',
            'item_id': 'Asset ID',
            'keeper': 'Keeper',
            'chip_code': 'Chip Code',
            'location': 'Location',
            'note': 'Note'
        })
        csv = export_df.to_csv(index=False).encode('utf-8-sig')
        st.download_button("Download CSV", csv, "tivo_inventory_cloud.csv", "text/csv")

    else:
        st.info("Sheet is empty. Add data from sidebar.")

if __name__ == '__main__':
    main()

