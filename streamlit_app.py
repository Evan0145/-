import streamlit as st
import pandas as pd
from PIL import Image, ImageDraw, ImageFont

# 頁面配置
st.set_page_config(page_title="AI 智能木工拆單系統", layout="wide")

# 定義常數 (mm)
SHEET_W, SHEET_H = 2440, 1220

# 側邊欄：輸入參數
st.sidebar.header("🛠️ AI 設計參數")
uploaded_file = st.sidebar.file_uploader("1. 上傳設計草圖", type=["jpg", "png", "jpeg"])

if st.sidebar.button("✨ AI 識別並分析圖紙") and uploaded_file:
    st.sidebar.success("✅ 已根據圖面自動填入建議數值")
    # 這裡可接入真正的 AI Vision API，目前模擬預設值
    job_name = f"AI_分析_{uploaded_file.name.split('.')[0]}"
else:
    job_name = "未命名案名"

st.sidebar.divider()

name = st.sidebar.text_input("案名", value=job_name)
col1, col2 = st.sidebar.columns(2)
w = col1.number_input("總寬 W (mm)", value=1200)
h = col2.number_input("總高 H (mm)", value=900)
d = col1.number_input("總深 D (mm)", value=450)
bh = col2.number_input("腳座高度 (mm)", value=100)

# --- 核心邏輯：拆單計算 ---
parts = [
    {"name": "側板", "l": h - bh, "w": d, "qty": 2, "color": "#f37021"},
    {"name": "頂/底板", "l": w - 36, "w": d, "qty": 2, "color": "#2c3e50"},
    {"name": "背板", "l": h - bh - 6, "w": w - 6, "qty": 1, "color": "#95a5a6"},
    {"name": "門板", "l": h - bh - 4, "w": (w/2) - 3, "qty": 2, "color": "#7f8c8d"}
]

# --- 核心邏輯：排版計算 ---
def run_nesting(parts):
    sorted_items = []
    for p in parts:
        for _ in range(int(p['qty'])):
            sorted_items.append(p)
    sorted_items.sort(key=lambda x: x['l'], reverse=True)

    draw_list = []
    cur_x, cur_y = 20, 20
    col_max_w = 0
    used_area = 0
    is_over = False

    for p in sorted_items:
        if cur_y + p['l'] + 20 > SHEET_H:
            cur_y = 20
            cur_x += col_max_w + 20
            col_max_w = 0
        
        if cur_x + p['w'] + 20 > SHEET_W:
            is_over = True
            break
        
        draw_list.append({'rect': [cur_x, cur_y, cur_x + p['w'], cur_y + p['l']], 'color': p['color'], 'name': p['name']})
        cur_y += p['l'] + 20
        col_max_w = max(col_max_w, p['w'])
        used_area += (p['l'] + 4) * (p['w'] + 4)
    
    usage_rate = (used_area / (SHEET_W * SHEET_H)) * 100
    return draw_list, usage_rate, is_over

draw_list, rate, is_over = run_nesting(parts)

# --- 右側顯示區域 ---
st.title("📊 木工排料實時預覽")

# 利用率進度條
st.write(f"板材利用率: **{rate:.1f}%**")
st.progress(min(rate/100, 1.0))

if is_over:
    st.error("⚠️ 警告：目前尺寸已超出 4x8 板材範圍！")

# 繪製圖形
img = Image.new('RGB', (SHEET_W, SHEET_H), "#ffffff")
draw = ImageDraw.Draw(img)
# 畫板材邊框
draw.rectangle([0, 0, SHEET_W, SHEET_H], outline="#2c3e50", width=10)

for p in draw_list:
    draw.rectangle(p['rect'], fill=p['color'], outline="white", width=2)

# 在手機上顯示縮放後的圖片
st.image(img, caption=f"4x8 板材排版圖 (案名: {name})", use_container_width=True)

# 零件清單表格
st.subheader("📋 零件清單")
df = pd.DataFrame(parts)[['name', 'l', 'w', 'qty']]
df.columns = ['零件名稱', '長度 (L)', '寬度 (W)', '數量']
st.table(df)

# 下載功能
csv = df.to_csv(index=False).encode('utf_8_sig')
st.download_button("📥 下載拆單 CSV", csv, "parts_list.csv", "text/csv")