import streamlit as st
import pandas as pd
from PIL import Image, ImageDraw
from rectpack import newPacker
import sqlite3
import json
from datetime import datetime
import os
import numpy as np

# --- 0. 資料庫初始化 (新增 project_name 案場名稱欄位) ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_NAME = os.path.join(BASE_DIR, "furniture_logic.db")

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    # 建立初始表
    c.execute('''CREATE TABLE IF NOT EXISTS design_history 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  project_name TEXT, cab_type TEXT, 
                  total_w REAL, total_h REAL, thick REAL, 
                  logic_json TEXT, timestamp DATETIME)''')
    
    # 補救邏輯：如果舊資料庫沒欄位，自動 ALTER TABLE
    try:
        c.execute("ALTER TABLE design_history ADD COLUMN project_name TEXT")
    except sqlite3.OperationalError:
        pass # 代表欄位已經存在
    
    conn.commit()
    conn.close()

init_db()

# --- 1. AI 預測引擎 ---
def ai_logic_prediction(cab_type, current_w, current_h, current_thick):
    try:
        conn = sqlite3.connect(DB_NAME)
        query = "SELECT total_w, total_h, thick, logic_json FROM design_history WHERE cab_type = ?"
        df = pd.read_sql_query(query, conn, params=(cab_type,))
        conn.close()
        if df.empty or len(df) < 3: return None
        all_samples = []
        for _, row in df.iterrows():
            parts = json.loads(row['logic_json'])
            all_samples.append({"base_w": row['total_w'], "base_h": row['total_h'], "parts": parts})
        unique_part_names = set(p['名稱'] for s in all_samples for p in s['parts'])
        predicted_parts = []
        for p_name in unique_part_names:
            offsets_w, offsets_h, counts, edges = [], [], [], []
            for s in all_samples:
                for p in s['parts']:
                    if p['名稱'] == p_name:
                        offsets_w.append(s['base_w'] - p['寬W'])
                        offsets_h.append(s['base_h'] - p['高H'])
                        counts.append(p['數量'])
                        edges.append(p['封邊'])
            predicted_parts.append({
                "名稱": p_name, "寬W": float(current_w - np.median(offsets_w)),
                "高H": float(current_h - np.median(offsets_h)),
                "數量": int(np.median(counts)), "封邊": max(set(edges), key=edges.count)
            })
        return predicted_parts
    except: return None

# --- 2. 原始手動公式 (備案) ---
def manual_decompose(cab_type, total_w, total_h, thick):
    if cab_type == "客廳櫃":
        return [{"名稱": "客廳-側板", "寬W": total_h, "高H": 400.0, "數量": 2, "封邊": "長邊x2"},
                {"名稱": "客廳-底板", "寬W": total_w - (thick * 2), "高H": 400.0, "數量": 2, "封邊": "長邊x1"}]
    elif cab_type == "衣櫃":
        return [{"名稱": "衣櫃-側板", "寬W": total_h, "高H": 600.0, "數量": 2, "封邊": "長邊x2"},
                {"名稱": "衣櫃-頂底板", "寬W": total_w - (thick * 2), "高H": 600.0, "數量": 2, "封邊": "長邊x1"}]
    return []

# --- 3. 核心繪圖函式 ---
def draw_sheet(bin_data, sw, sh, active_color, scale=0.3):
    margin = 50
    img = Image.new('RGB', (int(sw*scale)+margin*2, int(sh*scale)+margin*2), "#FFFFFF")
    draw = ImageDraw.Draw(img)
    draw.rectangle([margin, margin, margin+sw*scale, margin+sh*scale], outline="#000", fill="#F0F0F0", width=3)
    
    def draw_dashed_line(xy):
        x1, y1, x2, y2 = xy
        l = ((x2-x1)**2 + (y2-y1)**2)**0.5
        if l == 0: return
        dx, dy = (x2-x1)/l, (y2-y1)/l
        for i in range(0, int(l), 12):
            s, e = i, min(i+6, l)
            draw.line([(x1+s*dx, y1+s*dy), (x1+e*dx, y1+e*dy)], fill="#FF3D00", width=5)

    for r in bin_data['rects']:
        x1, y1 = margin + r['x']*scale, margin + r['y']*scale
        x2, y2 = margin + (r['x']+r['w'])*scale, margin + (r['y']+r['h'])*scale
        draw.rectangle([x1, y1, x2, y2], fill=active_color, outline="black", width=2)
        edge = str(r['edge'])
        is_landscape = (x2 - x1) >= (y2 - y1)
        if "全封" in edge:
            draw_dashed_line((x1, y1, x2, y1)); draw_dashed_line((x1, y2, x2, y2))
            draw_dashed_line((x1, y1, x1, y2)); draw_dashed_line((x2, y1, x2, y2))
        else:
            if is_landscape:
                if "長邊x1" in edge: draw_dashed_line((x1, y1, x2, y1))
                if "長邊x2" in edge: draw_dashed_line((x1, y1, x2, y1)); draw_dashed_line((x1, y2, x2, y2))
                if "短邊x1" in edge: draw_dashed_line((x1, y1, x1, y2))
                if "短邊x2" in edge: draw_dashed_line((x1, y1, x1, y2)); draw_dashed_line((x2, y1, x2, y2))
            else:
                if "長邊x1" in edge: draw_dashed_line((x1, y1, x1, y2))
                if "長邊x2" in edge: draw_dashed_line((x1, y1, x1, y2)); draw_dashed_line((x2, y1, x2, y2))
                if "短邊x1" in edge: draw_dashed_line((x1, y1, x2, y1))
                if "短邊x2" in edge: draw_dashed_line((x1, y1, x2, y1)); draw_dashed_line((x1, y2, x2, y2))
        if (x2-x1) > 40:
            draw.text((x1+5, y1+5), f"{r['name']}\n{int(r['w'])}x{int(r['h'])}", fill="black")
    return img

# --- 4. 側邊欄與設定 ---
st.set_page_config(page_title="AI 家具智慧生產系統", layout="wide")
with st.sidebar:
    st.header("🧱 材料設定")
    wood_skin = st.selectbox("板材貼皮", ["白橡木", "胡桃木", "純白", "灰色", "黑木紋"])
    board_thick = st.selectbox("板材厚度 (mm)", [18.0, 15.0, 25.0])
    sw, sh = st.number_input("板材長度 W", value=2440), st.number_input("板材寬度 H", value=1220)
    board_price = st.number_input("板材單價", value=1500)
    kerf = st.slider("鋸路損耗 (mm)", 0, 10, 3)
    if os.path.exists(DB_NAME):
        with open(DB_NAME, "rb") as f:
            st.download_button("📥 下載資料庫檔案", data=f, file_name="furniture_logic.db")

active_color = {"白橡木": "#D2B48C", "胡桃木": "#5D4037", "純白": "#F5F5F5", "灰色": "#9E9E9E", "黑木紋": "#212121"}[wood_skin]

# --- 5. 主頁面：智慧拆料 ---
if 'all_parts' not in st.session_state: st.session_state.all_parts = []

col_input, col_preview = st.columns([1, 1.2])

with col_input:
    st.subheader("🔨 智慧拆料與邏輯儲存")
    # --- 新增案場名稱輸入框 ---
    p_name = st.text_input("📝 案場名稱 (選填)", placeholder="例如：林先生-臥室衣櫃")
    
    c_type = st.selectbox("選擇櫃型", ["客廳櫃", "衣櫃", "鞋櫃", "自定義"])
    tw, th = st.number_input("總寬 (W)", value=800.0), st.number_input("總高 (H)", value=1200.0)
    
    c1, c2 = st.columns(2)
    with c1:
        if st.button("🤖 AI 邏輯預測", use_container_width=True):
            prediction = ai_logic_prediction(c_type, tw, th, board_thick)
            if prediction: st.session_state.all_parts = prediction
            else: st.warning("數據不足，請先用手動公式累積數據")
    with c2:
        if st.button("✨ 手動公式拆料", use_container_width=True):
            st.session_state.all_parts = manual_decompose(c_type, tw, th, board_thick)
            st.rerun()

    st.divider()
    edge_list = ["不封邊", "長邊x1", "長邊x2", "短邊x1", "短邊x2", "全封"]
    st.session_state.all_parts = st.data_editor(
        st.session_state.all_parts, num_rows="dynamic", use_container_width=True,
        column_config={"封邊": st.column_config.SelectboxColumn("封邊選項", options=edge_list, required=True)}
    )

    cc1, cc2 = st.columns(2)
    with cc1:
        if st.button("💾 儲存此邏輯至資料庫", use_container_width=True):
            with sqlite3.connect(DB_NAME) as conn:
                # 插入資料時包含 project_name
                conn.execute("INSERT INTO design_history (project_name, cab_type, total_w, total_h, thick, logic_json, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?)",
                          (p_name, c_type, tw, th, board_thick, json.dumps(st.session_state.all_parts, ensure_ascii=False), datetime.now()))
            st.balloons()
            st.success(f"已儲存案場：{p_name if p_name else '未命名'}")
    with cc2:
        if st.button("🗑️ 清空零件表", use_container_width=True):
            st.session_state.all_parts = []
            st.rerun()

with col_preview:
    st.subheader("📊 裁切排版分析")
    if st.session_state.all_parts:
        packer = newPacker(rotation=True)
        packer.add_bin(sw, sh, count=100)
        t_area = 0
        for row in st.session_state.all_parts:
            try:
                for _ in range(int(row['數量'])):
                    packer.add_rect(float(row['寬W'])+kerf, float(row['高H'])+kerf, rid=(row['名稱'], row['封邊']))
                    t_area += (float(row['寬W']) * float(row['高H']))
            except: continue
        packer.pack()
        all_bins = []
        for b in packer:
            if len(b) > 0:
                rects = [{"x":r.x, "y":r.y, "w":r.width-kerf, "h":r.height-kerf, "name":r.rid[0], "edge":r.rid[1]} for r in b]
                all_bins.append({"rects": rects})
        if all_bins:
            num_s = len(all_bins)
            rate = (t_area / (sw * sh * num_s)) * 100
            m1, m2, m3 = st.columns(3)
            m1.metric("板材片數", f"{num_s} 片")
            m2.metric("利用率", f"{rate:.1f}%")
            m3.metric("預估費用", f"${int(num_s * board_price)}")
            for i, bin_data in enumerate(all_bins):
                st.write(f"第 {i+1} 張板材配置")
                st.image(draw_sheet(bin_data, sw, sh, active_color), use_container_width=True)
    else: st.info("💡 尚未有零件，請點擊拆料按鈕。")

# --- 6. 案場詳細數據管理面板 ---
st.divider()
st.subheader("📂 案場數據管理與零件明細")
try:
    conn = sqlite3.connect(DB_NAME)
    # 讀取完整歷史紀錄
    df_history = pd.read_sql_query("""
        SELECT id, project_name AS 案場, cab_type AS 櫃型, 
               total_w AS 總寬, total_h AS 總高, thick AS 板厚,
               logic_json, timestamp AS 時間 
        FROM design_history ORDER BY id DESC
    """, conn)
    
    if not df_history.empty:
        # 1. 顯示主列表 (隱藏 logic_json 欄位避免混亂)
        st.dataframe(df_history.drop(columns=['logic_json']), use_container_width=True)
        
        # 2. 詳細零件透視區
        st.write("🔍 **零件明細查詢**")
        col_select, col_actions = st.columns([1, 1])
        
        with col_select:
            selected_id = st.selectbox("請選擇要查看明細的 ID", df_history['id'].tolist())
            
            # 根據選擇的 ID 抓取 JSON 並轉回表格
            target_row = df_history[df_history['id'] == selected_id].iloc[0]
            detailed_parts = json.loads(target_row['logic_json'])
            df_detail = pd.DataFrame(detailed_parts)
            
            # 顯示該案場的詳細零件表
            st.info(f"案場：{target_row['案場']} | 櫃型：{target_row['櫃型']} | 尺寸：{target_row['總寬']}x{target_row['總高']}")
            st.table(df_detail) # 使用靜態表格呈現詳細數據

        with col_actions:
            st.write("⚙️ **管理操作**")
            # 刪除功能
            if st.button(f"🗑️ 刪除 ID: {selected_id} 的紀錄"):
                c = conn.cursor()
                c.execute("DELETE FROM design_history WHERE id=?", (selected_id,))
                conn.commit()
                st.success(f"已刪除 ID {selected_id}")
                st.rerun()
                
            # 重載功能：將歷史數據推回工作區
            if st.button(f"🔄 將此案場數據載入工作區 (編輯)"):
                st.session_state.all_parts = detailed_parts
                st.success("數據已載入上方編輯區，您可以重新計算排版！")
                st.rerun()

            if st.button("🧨 清空所有歷史紀錄"):
                if st.checkbox("我確認要刪除所有數據 (不可恢復)"):
                    c = conn.cursor()
                    c.execute("DELETE FROM design_history")
                    conn.commit()
                    st.rerun()
    else:
        st.info("💡 目前資料庫尚無數據。")
    conn.close()
except Exception as e:
    st.error(f"管理面板讀取失敗: {e}")