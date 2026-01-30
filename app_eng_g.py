import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import time

# --- Google Sheets Setup ---
# 設定試算表名稱 (請確認跟你的 Google Sheet 檔名一致)
SHEET_NAME = "Tivo_Inventory_DB"

def get_connection():
    """連線到 Google Sheets"""
    # 從 secrets.toml 讀取設定
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

# --- CRUD Operations (Modified for Google Sheets) ---

def get_options(sheet_name):
    try:
        ws = get_worksheet(sheet_name)
        # 讀取第一欄的所有值，並去掉標題
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
    
    # 處理日期格式
    if not df.empty and 'date' in df.columns:
        df['date'] = pd.to_datetime(df['date'], errors='coerce').dt.date
    
    # 確保 ID 是數字 (如果有的話)
    if not df.empty and 'id' in df.columns:
         df['id'] = pd.to_numeric(df['id'], errors='coerce')

    return df

def add_data(date, item_name, item_id, keeper, chip_code, location):
    ws = get_worksheet("items")
    # 自動產生 ID (取當前行數+1 或是用 Timestamp，這裡簡單用 Timestamp 確保唯一性)
    new_id = int(datetime.now().timestamp())
    
    # Google Sheets 寫入時，日期最好轉成字串
    date_str = date.strftime("%Y-%m-%d")
    
    ws.append_row([new_id, date_str, item_name, item_id, keeper, chip_code, location])

def update_data(target_id, date, item_name, item_id, keeper, chip_code, location):
    ws = get_worksheet("items")
    # 尋找目標 ID 所在的行數
    # 注意：get_all_records 讀出來是 list of dicts
    # 為了效能，我們先讀整張表，在 Python 裡找位置，再更新
    cell = ws.find(str(target_id), in_column=1) # 假設 ID 在第一欄
    
    if cell:
        row_num = cell.row
        date_str = date.strftime("%Y-%m-%d") if hasattr(date, 'strftime') else str(date)
        # 更新該行的內容 (注意欄位順序要跟 headers 一樣)
        # A=id, B=date, C=name, D=item_id, E=keeper, F=chip, G=loc
        ws.update(f"B{row_num}:G{row_num}", [[date_str, item_name, item_id, keeper, chip_code, location]])

def delete_data(target_id):
    ws = get_worksheet("items")
    cell = ws.find(str(target_id), in_column=1)
    if cell:
        ws.delete_rows(cell.row)

# --- UI (Same as before) ---

def main():
    st.set_page_config(page_title="Tivo DK Inventory (Cloud)", layout="wide")
 # --- 👇 加入這段 CSS 語法開始 👇 ---
    hide_st_style = """
        <style>
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;}
        </style>
        """
    st.markdown(hide_st_style, unsafe_allow_html=True)
    # --- 👆 加入這段 CSS 語法結束 👆 ---

    init_db()
    

    st.title("☁️ Tivo Development Kit Inventory System")
    st.caption("Data is synced directly to Google Sheets.")
    st.markdown("---")

    # 快取選項以避免頻繁讀取 API
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
            st.text_input("Prefix", "VEWD-", disabled=True)
        with col_num:
            input_id_num = st.text_input("ID Number", placeholder="e.g., 1001")
        
        input_keeper = st.text_input("Keeper", placeholder="e.g., John Doe")
        
        # 使用 Session State 的選項
        input_chip = st.selectbox("Chip Code", st.session_state.chip_options)
        input_loc = st.selectbox("Location", st.session_state.location_options)

        if st.button("Submit", type="primary"):
            if input_name and input_id_num:
                with st.spinner("Saving to Google Sheets..."):
                    full_id = f"VEWD-{input_id_num}"
                    add_data(input_date, input_name, full_id, input_keeper, input_chip, input_loc)
                    st.success(f"Added: {full_id}")
                    time.sleep(1) # 等待 Google Sheet 更新
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
                            st.session_state.chip_options = get_options('chips') # 重新讀取
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
                "id": None,
                "date": st.column_config.DateColumn("Date"),
                "item_name": st.column_config.TextColumn("Item Name"),
                "item_id": st.column_config.TextColumn("Full ID"),
                "keeper": st.column_config.TextColumn("Keeper"),
                "chip_code": st.column_config.SelectboxColumn("Chip", options=st.session_state.chip_options, required=True),
                "location": st.column_config.SelectboxColumn("Loc", options=st.session_state.location_options, required=True)
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
                                # 檢查是否真的有變動會比較複雜，這裡簡單起見直接更新未刪除的行
                                # 實際專案建議做 diff check
                                update_data(
                                    row_id, row['date'], row['item_name'], 
                                    row['item_id'], row['keeper'], 
                                    row['chip_code'], row['location']
                                )
                    st.toast("✅ Google Sheets Updated!")
                    time.sleep(1)
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")

        # --- Export ---
        st.markdown("### 📥 Export")
        export_df = df.drop(columns=['Delete?', 'id'])
        csv = export_df.to_csv(index=False).encode('utf-8-sig')
        st.download_button("Download CSV", csv, "tivo_inventory_cloud.csv", "text/csv")

    else:
        st.info("Sheet is empty. Add data from sidebar.")

if __name__ == '__main__':

    main()


