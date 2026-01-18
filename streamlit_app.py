import streamlit as st
import pandas as pd
from PIL import Image, ImageDraw
from rectpack import newPacker

# 設定頁面
st.set_page_config(page_title="AI 家具生產系統", layout="wide")

# --- 0. CSS 放大字體與美化 ---
st.markdown("""
    <style>
    html, body, [class*="st-"] { font-size: 1.15rem; }
    .stMetric label { font-size: 1.4rem !important; color: #555; }
    .stMetric div { font-size: 2.2rem !important; font-weight: bold; }
    h1 { font-size: 2.8rem !important; color: #1E88E5; }
    </style>
    """, unsafe_allow_html=True)

# --- 1. 定義拆分邏輯 ---
def decompose_cabinet(cab_type, total_w, total_h, thick):
    if cab_type == "客廳櫃":
        return [
            {"名稱": "客廳-側板", "寬W": total_h, "高H": 400, "數量": 2, "封邊": "長邊x2"},
            {"名稱": "客廳-底板", "寬W": total_w - (thick * 2), "高H": 400, "數量": 2, "封邊": "長邊x1"}
        ]
    elif cab_type == "衣櫃":
        return [
            {"名稱": "衣櫃-側板", "寬W": total_h, "高H": 600, "數量": 2, "封邊": "長邊x2"},
            {"名稱": "衣櫃-頂底板", "寬W": total_w - (thick * 2), "高H": 600, "數量": 2, "封邊": "長邊x1"}
        ]
    elif cab_type == "鞋櫃":
        return [
            {"名稱": "鞋櫃-側板", "寬W": total_h, "高H": 350, "數量": 2, "封邊": "長邊x2"},
            {"名稱": "鞋櫃-頂底板", "寬W": total_w - (thick * 2), "高H": 350, "數量": 2, "封邊": "長邊x1"}
        ]
    return []

# --- 2. 核心繪圖函式 (顏色與字體優化) ---
def draw_sheet(bin_data, sw, sh, active_color, text_color, scale=0.3):
    margin = 50
    img = Image.new('RGB', (int(sw*scale)+margin*2, int(sh*scale)+margin*2), "#FFFFFF")
    draw = ImageDraw.Draw(img)
    # 畫大底板
    draw.rectangle([margin, margin, margin+sw*scale, margin+sh*scale], outline="#000", fill="#F0F0F0", width=3)
    
    def draw_dashed_line(xy):
        x1, y1, x2, y2 = xy
        line_len = ((x2-x1)**2 + (y2-y1)**2)**0.5
        if line_len == 0: return
        dx, dy = (x2-x1)/line_len, (y2-y1)/line_len
        for i in range(0, int(line_len), 12):
            s, e = i, min(i + 6, line_len)
            draw.line([(x1+s*dx, y1+s*dy), (x1+e*dx, y1+e*dy)], fill="#FF3D00", width=5)

    for r in bin_data['rects']:
        x1, y1, x2, y2 = margin+r['x']*scale, margin+r['y']*scale, margin+(r['x']+r['w'])*scale, margin+(r['y']+r['h'])*scale
        
        # 根據物件類別上色 (結合板材色與透明度感)
        name = r['name']
        rect_fill = active_color
        if "客廳" in name: rect_fill = "#90CAF9" # 亮藍
        elif "衣櫃" in name: rect_fill = "#A5D6A7" # 亮綠
        elif "鞋櫃" in name: rect_fill = "#FFF59D" # 亮黃
        
        draw.rectangle([x1, y1, x2, y2], fill=rect_fill, outline="black", width=2)
        
        # 封邊虛線
        e = str(r['edge'])
        if "長邊x1" in e or "全封" in e: draw_dashed_line((x1, y1, x1, y2))
        if "長邊x2" in e or "全封" in e: draw_dashed_line((x1, y1, x1, y2)); draw_dashed_line((x2, y1, x2, y2))
        if "短邊x1" in e or "全封" in e: draw_dashed_line((x1, y1, x2, y1))
        if "短邊x2" in e or "全封" in e: draw_dashed_line((x1, y1, x2, y1)); draw_dashed_line((x1, y2, x2, y2))

        # 字體顯示強化
        if r['w'] * scale > 40:
            txt = f"{name}\n{int(r['w'])}x{int(r['h'])}"
            # 加粗效果
            for off in [(0,0), (1,0), (0,1)]:
                draw.text((x1+8+off[0], y1+8+off[1]), txt, fill="black") # 預覽圖字體統一用黑框感較清楚
            
    return img

# --- 3. 側邊欄 ---
with st.sidebar:
    st.header("🧱 材料與成本設定")
    wood_skin = st.selectbox("板材貼皮/顏色", ["白橡木", "胡桃木", "純白", "灰色", "黑木紋"])
    board_thick = st.selectbox("板材厚度 (mm)", [18, 15, 25, 5])
    sw = st.number_input("板材長度 W (mm)", value=2440)
    sh = st.number_input("板材寬度 H (mm)", value=1220)
    st.divider()
    board_price = st.number_input("板材單價 (元)", value=1500)
    skin_cost_m2 = st.number_input("貼皮加價 (元/m²)", value=200)
    kerf = st.slider("鋸路損耗 (mm)", 0, 10, 3)
    allow_rot = st.checkbox("允許旋轉零件", value=True)

skin_colors = {"白橡木": "#D2B48C", "胡桃木": "#5D4037", "純白": "#F5F5F5", "灰色": "#9E9E9E", "黑木紋": "#212121"}
active_color = skin_colors[wood_skin]
text_color = "white" if wood_skin in ["胡桃木", "黑木紋"] else "black"

# --- 4. 主頁面 ---
if 'all_parts' not in st.session_state:
    st.session_state.all_parts = []

col_input, col_preview = st.columns([1, 1.1])

with col_input:
    st.subheader("🔨 快速物件拆解")
    cab_type = st.selectbox("選擇櫃型", ["--- 手動新增零件 ---", "客廳櫃", "衣櫃", "鞋櫃"])
    
    if cab_type != "--- 手動新增零件 ---":
        c1, c2, c3 = st.columns(3)
        tw = c1.number_input("總寬 (W)", value=800)
        th = c2.number_input("總高 (H)", value=1200)
        if c3.button("✨ 點擊拆料"):
            st.session_state.all_parts.extend(decompose_cabinet(cab_type, tw, th, board_thick))
            st.rerun()
    
    st.markdown("---")
    st.subheader("📋 裁切明細表")
    
    # 封邊選項設定 (更動：拉選項)
    edge_list = ["不封邊", "長邊x1", "長邊x2", "短邊x1", "短邊x2", "全封"]
    
    df_input = st.data_editor(
        st.session_state.all_parts,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "封邊": st.column_config.SelectboxColumn("封邊選項", options=edge_list, required=True),
            "寬W": st.column_config.NumberColumn("寬W", min_value=1),
            "高H": st.column_config.NumberColumn("高H", min_value=1),
            "數量": st.column_config.NumberColumn("數量", min_value=1)
        },
        key="main_editor"
    )
    st.session_state.all_parts = df_input 

    if st.button("🗑️ 清空所有零件"):
        st.session_state.all_parts = []
        st.rerun()

with col_preview:
    packer = newPacker(rotation=allow_rot)
    packer.add_bin(sw, sh, count=100)
    total_area = 0
    
    if st.session_state.all_parts:
        for row in st.session_state.all_parts:
            try:
                w, h, q = float(row['寬W']), float(row['高H']), int(row['數量'])
                for _ in range(q):
                    packer.add_rect(w + kerf, h + kerf, rid=(row['名稱'], row['封邊']))
                    total_area += (w * h)
            except: continue
        packer.pack()

    all_bins = []
    for b in packer:
        if len(b) > 0:
            rects = [{"x":r.x, "y":r.y, "w":r.width-kerf, "h":r.height-kerf, "name":r.rid[0], "edge":r.rid[1]} for r in b]
            all_bins.append({"rects": rects})

    if all_bins:
        num_s = len(all_bins)
        rate = (total_area / (sw * sh * num_s)) * 100
        
        st.subheader("📊 裁切排版分析")
        m1, m2, m3 = st.columns(3)
        m1.metric("板材片數", f"{num_s} 片")
        m2.metric("利用率", f"{rate:.1f}%")
        m3.metric("未使用率", f"{100 - rate:.1f}%")

        for i, bin_data in enumerate(all_bins):
            st.write(f"**第 {i+1} 張板材配置**")
            st.image(draw_sheet(bin_data, sw, sh, active_color, text_color), use_container_width=True)

        st.divider()
        st.subheader("💰 預算分析")
        skin_c = (total_area / 1000000) * skin_cost_m2
        cc1, cc2 = st.columns(2)
        cc1.info(f"板材費用: **${int(num_s * board_price)}**")
        cc2.success(f"總計估計: **${int((num_s * board_price) + skin_c)}**")
    else:
        st.info("💡 尚未有零件，請從左側添加或手動輸入尺寸。")