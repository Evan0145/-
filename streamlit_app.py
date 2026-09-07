import streamlit as st
import pandas as pd
from PIL import Image, ImageDraw
from rectpack import newPacker
import sqlite3
import json
from datetime import datetime
import os
import numpy as np

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_NAME = os.path.join(BASE_DIR, "furniture_logic.db")

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS design_history 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  cab_type TEXT, total_w REAL, total_h REAL, thick REAL, 
                  logic_json TEXT, timestamp DATETIME)''')
    conn.commit()
    conn.close()

init_db()

def ai_logic_prediction(cab_type, current_w, current_h, current_thick):
    """從資料庫學習偏移量規律並預測零件尺寸"""
    try:
        conn = sqlite3.connect(DB_NAME)
        query = "SELECT total_w, total_h, thick, logic_json FROM design_history WHERE cab_type = ?"
        df = pd.read_sql_query(query, conn, params=(cab_type,))
        conn.close()

        if df.empty or len(df) < 3: 
            return None

        all_samples = []
        for _, row in df.iterrows():
            parts = json.loads(row['logic_json'])
            all_samples.append({
                "base_w": row['total_w'], "base_h": row['total_h'],
                "base_t": row['thick'], "parts": parts
            })

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
            
            pred_w = current_w - np.median(offsets_w)
            pred_h = current_h - np.median(offsets_h)
            
            predicted_parts.append({
                "名稱": p_name,
                "寬W": float(pred_w),
                "高H": float(pred_h),
                "數量": int(np.median(counts)),
                "封邊": max(set(edges), key=edges.count)
            })
        return predicted_parts
    except:
        return None

def manual_decompose(cab_type, total_w, total_h, thick):
    if cab_type == "客廳櫃":
        return [{"名稱": "客廳-側板", "寬W": total_h, "高H": 400.0, "數量": 2, "封邊": "長邊x2"},
                {"名稱": "客廳-底板", "寬W": total_w - (thick * 2), "高H": 400.0, "數量": 2, "封邊": "長邊x1"}]
    elif cab_type == "衣櫃":
        return [{"名稱": "衣櫃-側板", "寬W": total_h, "高H": 600.0, "數量": 2, "封邊": "長邊x2"},
                {"名稱": "衣櫃-頂底板", "寬W": total_w - (thick * 2), "高H": 600.0, "數量": 2, "封邊": "長邊x1"}]
    return []

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
            draw.line([(x1+s*dx, y1+s*dy), (x1+e*dx, y1+e*dy)], fill="#FF3D00", width=5) # 橘色加粗虛線

    for r in bin_data['rects']:
        x1, y1 = margin + r['x']*scale, margin + r['y']*scale
        x2, y2 = margin + (r['x']+r['w'])*scale, margin + (r['y']+r['h'])*scale
        
        draw.rectangle([x1, y1, x2, y2], fill=active_color, outline="black", width=2)
        
        edge = str(r['edge']) 
        
        is_landscape = (x2 - x1) >= (y2 - y1)
        
        if "全封" in edge:
            draw_dashed_line((x1, y1, x2, y1)); draw_dashed_line((x1, y2, x2, y2)) # 上下
            draw_dashed_line((x1, y1, x1, y2)); draw_dashed_line((x2, y1, x2, y2)) # 左右
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

        # 標註文字
        if (x2-x1) > 30:
            draw.text((x1+5, y1+5), f"{r['name']}\n{int(r['w'])}x{int(r['h'])}", fill="black")
            
    return img
    
st.set_page_config(page_title="AI 家具智慧生產系統", layout="wide")
with st.sidebar:
    st.header("🧱 材料設定")
    wood_skin = st.selectbox("板材貼皮", ["白橡木", "胡桃木", "純白", "灰色", "黑木紋"])
    board_thick = st.selectbox("板材厚度 (mm)", [18.0, 15.0, 25.0])
    sw = st.number_input("板材長度 W (mm)", value=2440)
    sh = st.number_input("板材寬度 H (mm)", value=1220)
    board_price = st.number_input("板材單價", value=1500)
    kerf = st.slider("鋸路損耗 (mm)", 0, 10, 3)
    
    st.divider()
    if os.path.exists(DB_NAME):
        with open(DB_NAME, "rb") as f:
            st.download_button("📥 下載資料庫檔案", data=f, file_name="furniture_logic.db")

skin_colors = {"白橡木": "#D2B48C", "胡桃木": "#5D4037", "純白": "#F5F5F5", "灰色": "#9E9E9E", "黑木紋": "#212121"}
active_color = skin_colors[wood_skin]

if 'all_parts' not in st.session_state: st.session_state.all_parts = []

col_input, col_preview = st.columns([1, 1.2])

with col_input:
    st.subheader("🔨 智慧拆料與邏輯儲存")
    c_type = st.selectbox("選擇櫃型", ["客廳櫃", "衣櫃", "鞋櫃", "自定義"])
    tw = st.number_input("總寬 (W)", value=800.0)
    th = st.number_input("總高 (H)", value=1200.0)
    
    c1, c2 = st.columns(2)
    with c1:
        if st.button("🤖 AI 邏輯預測", use_container_width=True):
            prediction = ai_logic_prediction(c_type, tw, th, board_thick)
            if prediction:
                st.session_state.all_parts = prediction
                st.toast("AI 已根據歷史數據推算尺寸")
            else:
                st.warning("數據不足 (需 3 筆)，請先用手動公式累積數據")

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
                conn.execute("INSERT INTO design_history (cab_type, total_w, total_h, thick, logic_json, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
                          (c_type, tw, th, board_thick, json.dumps(st.session_state.all_parts, ensure_ascii=False), datetime.now()))
            st.balloons()
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
    else:
        st.info("💡 尚未有零件，請點擊拆料按鈕或手動輸入尺寸。")
        
st.divider()
st.subheader("🛠️ 資料庫數據管理面板")
try:
    conn = sqlite3.connect(DB_NAME)
    df_history = pd.read_sql_query("SELECT * FROM design_history ORDER BY id DESC", conn)
    if not df_history.empty:
        st.dataframe(df_history, use_container_width=True)
        col_m1, col_m2 = st.columns(2)
        with col_m1:
            did = st.number_input("輸入要刪除的 ID", min_value=int(df_history['id'].min()), max_value=int(df_history['id'].max()), step=1)
            if st.button("🗑️ 刪除紀錄"):
                c = conn.cursor(); c.execute("DELETE FROM design_history WHERE id=?", (did,)); conn.commit(); st.rerun()
        with col_m2:
            if st.button("🧨 清空資料庫"):
                c = conn.cursor(); c.execute("DELETE FROM design_history"); conn.commit(); st.rerun()
    conn.close()
except: st.write("尚無數據")
