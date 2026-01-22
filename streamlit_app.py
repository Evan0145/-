import streamlit as st
import pandas as pd
from PIL import Image, ImageDraw
from rectpack import newPacker
import sqlite3
import json
from datetime import datetime
import os
import numpy as np

# --- 0. 資料庫初始化 (強化防錯版) ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_NAME = os.path.join(BASE_DIR, "furniture_logic.db")

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    # 確保 project_name 欄位在建立時就存在
    c.execute('''CREATE TABLE IF NOT EXISTS design_history 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  project_name TEXT, cab_type TEXT, 
                  total_w REAL, total_h REAL, thick REAL, 
                  logic_json TEXT, timestamp DATETIME)''')
    
    # 補救：如果舊表存在但沒欄位，手動增加
    try:
        c.execute("SELECT project_name FROM design_history LIMIT 1")
    except sqlite3.OperationalError:
        c.execute("ALTER TABLE design_history ADD COLUMN project_name TEXT DEFAULT ''")
    
    conn.commit()
    conn.close()

init_db()

# --- 1. 核心功能：AI 預測、繪圖 (維持不變) ---
def ai_logic_prediction(cab_type, current_w, current_h, current_thick):
    try:
        conn = sqlite3.connect(DB_NAME)
        df = pd.read_sql_query("SELECT total_w, total_h, thick, logic_json FROM design_history WHERE cab_type = ?", conn, params=(cab_type,))
        conn.close()
        if df.empty or len(df) < 3: return None
        all_samples = []
        for _, row in df.iterrows():
            all_samples.append({"base_w": row['total_w'], "base_h": row['total_h'], "parts": json.loads(row['logic_json'])})
        unique_part_names = set(p['名稱'] for s in all_samples for p in s['parts'])
        predicted_parts = []
        for p_name in unique_part_names:
            offsets_w, offsets_h, counts, edges = [], [], [], []
            for s in all_samples:
                for p in s['parts']:
                    if p['名稱'] == p_name:
                        offsets_w.append(s['base_w'] - p['寬W']); offsets_h.append(s['base_h'] - p['高H'])
                        counts.append(p['數量']); edges.append(p['封邊'])
            predicted_parts.append({"名稱": p_name, "寬W": float(current_w - np.median(offsets_w)), "高H": float(current_h - np.median(offsets_h)), "數量": int(np.median(counts)), "封邊": max(set(edges), key=edges.count)})
        return predicted_parts
    except: return None

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
        x1, y1, x2, y2 = margin+r['x']*scale, margin+r['y']*scale, margin+(r['x']+r['w'])*scale, margin+(r['y']+r['h'])*scale
        draw.rectangle([x1, y1, x2, y2], fill=active_color, outline="black", width=2)
        edge, is_landscape = str(r['edge']), (x2 - x1) >= (y2 - y1)
        if "全封" in edge:
            draw_dashed_line((x1, y1, x2, y1)); draw_dashed_line((x1, y2, x2, y2)); draw_dashed_line((x1, y1, x1, y2)); draw_dashed_line((x2, y1, x2, y2))
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
        if (x2-x1) > 40: draw.text((x1+5, y1+5), f"{r['name']}\n{int(r['w'])}x{int(r['h'])}", fill="black")
    return img

# --- 2. 主程式介面 ---
st.set_page_config(page_title="AI 家具生產系統", layout="wide")

if 'all_parts' not in st.session_state:
    st.session_state.all_parts = [{"名稱": "新零件", "寬W": 400.0, "高H": 300.0, "數量": 1, "封邊": "不封邊"}]

with st.sidebar:
    st.header("🧱 設定")
    wood_skin = st.selectbox("板材貼皮", ["白橡木", "胡桃木", "純白", "灰色", "黑木紋"])
    board_thick = st.selectbox("板材厚度 (mm)", [18.0, 15.0, 25.0])
    sw, sh = st.number_input("板長W", value=2440), st.number_input("板寬H", value=1220)
    board_price = st.number_input("單價", value=1500)
    kerf = st.slider("鋸路", 0, 10, 3)

active_color = {"白橡木": "#D2B48C", "胡桃木": "#5D4037", "純白": "#F5F5F5", "灰色": "#9E9E9E", "黑木紋": "#212121"}[wood_skin]

col_in, col_pre = st.columns([1, 1.2])

with col_in:
    st.subheader("🔨 拆料數據")
    p_name = st.text_input("📝 案場名稱", value="未命名案場")
    c_type = st.selectbox("櫃型", ["自定義", "客廳櫃", "衣櫃", "鞋櫃"])
    tw, th = st.number_input("總寬 W", value=800.0), st.number_input("總高 H", value=1200.0)
    
    c1, c2 = st.columns(2)
    with c1:
        if st.button("🤖 AI 預測"):
            res = ai_logic_prediction(c_type, tw, th, board_thick)
            if res: st.session_state.all_parts = res; st.rerun()
            else: st.warning("數據不足無法預測")
    with c2:
        if st.button("🗑️ 重置列表"):
            st.session_state.all_parts = [{"名稱": "新零件", "寬W": 0.0, "高H": 0.0, "數量": 1, "封邊": "不封邊"}]
            st.rerun()

    # 即時編輯表格
    st.session_state.all_parts = st.data_editor(
        st.session_state.all_parts, num_rows="dynamic", use_container_width=True,
        column_config={"封邊": st.column_config.SelectboxColumn("封邊", options=["不封邊", "長邊x1", "長邊x2", "短邊x1", "短邊x2", "全封"])}
    )

    if st.button(f"💾 儲存案場：{p_name}", use_container_width=True):
        with sqlite3.connect(DB_NAME) as conn:
            conn.execute("INSERT INTO design_history (project_name, cab_type, total_w, total_h, thick, logic_json, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?)",
                         (p_name, c_type, tw, th, board_thick, json.dumps(st.session_state.all_parts, ensure_ascii=False), datetime.now()))
        st.success("存檔成功")

with col_pre:
    st.subheader("📊 排版預覽")
    valid_parts = [p for p in st.session_state.all_parts if p.get('寬W', 0) > 0 and p.get('高H', 0) > 0]
    if valid_parts:
        packer = newPacker(rotation=True)
        packer.add_bin(sw, sh, count=100)
        t_area = 0
        for r in valid_parts:
            for _ in range(int(r['數量'])):
                packer.add_rect(float(r['寬W'])+kerf, float(r['高H'])+kerf, rid=(r['名稱'], r['封邊']))
                t_area += (float(r['寬W']) * float(r['高H']))
        packer.pack()
        all_bins = []
        for b in packer:
            if len(b) > 0:
                all_bins.append({"rects": [{"x":r.x, "y":r.y, "w":r.width-kerf, "h":r.height-kerf, "name":r.rid[0], "edge":r.rid[1]} for r in b]})
        if all_bins:
            st.metric("利用率", f"{(t_area/(sw*sh*len(all_bins)))*100:.1f}%", f"共 {len(all_bins)} 片")
            for i, bin_data in enumerate(all_bins):
                st.image(draw_sheet(bin_data, sw, sh, active_color), use_container_width=True)
    else: st.info("請在左側輸入寬高數據")

# --- 3. 管理面板 ---
st.divider()
st.subheader("📂 案場管理")
try:
    conn = sqlite3.connect(DB_NAME)
    df_h = pd.read_sql_query("SELECT id, project_name AS 案場, cab_type AS 櫃型, timestamp AS 時間 FROM design_history ORDER BY id DESC", conn)
    if not df_h.empty:
        st.dataframe(df_h, use_container_width=True)
        if st.button("🧨 清空資料庫"):
            c = conn.cursor(); c.execute("DELETE FROM design_history"); conn.commit(); st.rerun()
    conn.close()
except: pass