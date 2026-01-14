import streamlit as st
import pandas as pd
from PIL import Image, ImageDraw
from rectpack import newPacker

# 設定頁面
st.set_page_config(page_title="AI 家具生產系統", layout="wide")

# --- 1. CSS 優化：右側捲動區域與美化 ---
st.markdown("""
    <style>
    .scroll-container {
        max-height: 70vh;
        overflow-y: auto;
        padding: 15px;
        border: 2px solid #EEE;
        border-radius: 10px;
        background-color: #ffffff;
    }
    .metric-text { font-size: 1.2rem; font-weight: bold; color: #455A64; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. 左側邊欄：小標題介面 ---
with st.sidebar:
    st.markdown("## ⚙️ 系統設定")
    
    st.markdown("### 📦 板材與皮料設定")
    wood_skin = st.selectbox("板材貼皮/顏色", ["白橡木", "胡桃木", "純白", "灰色", "黑木紋"])
    board_thick = st.selectbox("板材厚度 (mm)", [18, 15, 25, 5])
    sw = st.number_input("板材寬度 W (mm)", value=2440)
    sh = st.number_input("板材高度 H (mm)", value=1220)

    st.markdown("---")
    st.markdown("### 💰 成本與裁切邏輯")
    board_price = st.number_input("板材單價 (元/片)", value=1500)
    skin_cost_m2 = st.number_input("貼皮成本 (元/m²)", value=200)
    kerf = st.slider("鋸路損耗 (mm)", 0, 10, 3)
    allow_rot = st.checkbox("允許 AI 旋轉零件", value=True)

# 配色定義
skin_colors = {"白橡木": "#D2B48C", "胡桃木": "#5D4037", "純白": "#F5F5F5", "灰色": "#9E9E9E", "黑木紋": "#212121"}
active_color = skin_colors[wood_skin]
text_color = "white" if wood_skin in ["胡桃木", "黑木紋"] else "black"

# --- 3. 核心繪圖函式 (補回這段預覽圖就不會不見) ---
def draw_sheet(bin_data, sw, sh, scale=0.3):
    margin = 40
    img_w, img_h = int(sw * scale) + margin * 2, int(sh * scale) + margin * 2
    img = Image.new('RGB', (img_w, img_h), "#FFFFFF")
    draw = ImageDraw.Draw(img)
    ox, oy = margin, margin
    
    # 畫底材外框
    draw.rectangle([ox, oy, ox + sw*scale, oy + sh*scale], outline="#333", width=2)
    
    edge_color = "#FF6D00" # 封邊橘色
    for r in bin_data['rects']:
        x1, y1, x2, y2 = ox+r['x']*scale, oy+r['y']*scale, ox+(r['x']+r['w'])*scale, oy+(r['y']+r['h'])*scale
        # 畫零件填充與黑框
        draw.rectangle([x1, y1, x2, y2], fill=active_color, outline="black", width=1)
        
        # 處理封邊 (長短邊、全封)
        e = r['edge']
        if "長邊x1" in e or "全封" in e: draw.line([x1+2, y1, x1+2, y2], fill=edge_color, width=4)
        if "長邊x2" in e or "全封" in e: draw.line([x1+2, y1, x1+2, y2], fill=edge_color, width=4); draw.line([x2-2, y1, x2-2, y2], fill=edge_color, width=4)
        if "短邊x1" in e or "全封" in e: draw.line([x1, y1+2, x2, y1+2], fill=edge_color, width=4)
        if "短邊x2" in e or "全封" in e: draw.line([x1, y1+2, x2, y1+2], fill=edge_color, width=4); draw.line([x1, y2-2, x2, y2-2], fill=edge_color, width=4)

        # 標註文字
        if r['w'] * scale > 40:
            draw.text((x1+5, y1+5), f"{r['name']}\n{int(r['w'])}x{int(r['h'])}", fill=text_color)
    return img

# --- 4. 主頁面佈局 ---
st.title("🖥️ 數位生產即時中控台")
col_input, col_preview = st.columns([1, 1.2])

with col_input:
    st.subheader("📝 裁切清單")
    common_names = ["側板", "頂板", "底板", "活動層板", "固定層板", "背板", "抽頭板", "抽牆板"]
    edge_options = ["不封邊", "長邊x1", "長邊x2", "短邊x1", "短邊x2", "全封"]
    
    df_input = st.data_editor(
        [
            {"名稱": "側板", "寬W": 450, "高H": 900, "數量": 4, "封邊": "長邊x2"},
            {"名稱": "層板", "寬W": 430, "高H": 560, "數量": 10, "封邊": "全封"}
        ],
        num_rows="dynamic", use_container_width=True, key="main_editor",
        column_config={
            "名稱": st.column_config.SelectboxColumn("名稱", options=common_names),
            "封邊": st.column_config.SelectboxColumn("封邊", options=edge_options)
        }
    )

# --- 5. 排版運算與結果呈現 ---
with col_preview:
    packer = newPacker(rotation=allow_rot)
    packer.add_bin(sw, sh, count=100)
    
    total_parts_area = 0
    current_df = pd.DataFrame(df_input)
    for _, row in current_df.iterrows():
        try:
            w, h, q = float(row['寬W']), float(row['高H']), int(row['數量'])
            for i in range(q):
                packer.add_rect(w + kerf, h + kerf, rid=(row['名稱'], row['封邊']))
                total_parts_area += (w * h)
        except: continue
    packer.pack()

    all_bins = []
    for b in packer:
        if len(b) > 0:
            rects = [{"x":r.x, "y":r.y, "w":r.width-kerf, "h":r.height-kerf, "name":r.rid[0], "edge":r.rid[1]} for r in b]
            all_bins.append({"rects": rects})

    if all_bins:
        num_sheets = len(all_bins)
        total_sheet_area = sw * sh * num_sheets
        usage_rate = (total_parts_area / total_sheet_area) * 100
        skin_total_cost = (total_parts_area / 1000000) * skin_cost_m2
        total_final_price = (num_sheets * board_price) + skin_total_cost

        # --- 利用率儀表板 ---
        st.subheader("📊 板材利用預估")
        st.progress(usage_rate / 100)
        c1, c2, c3 = st.columns(3)
        c1.metric("利用率", f"{usage_rate:.1f}%")
        c2.metric("已用面積", f"{total_parts_area/1000000:.2f} m²")
        c3.metric("剩餘面積", f"{(total_sheet_area - total_parts_area)/1000000:.2f} m²")

        # --- 捲軸預覽圖區 (補回繪圖調用) ---
        st.markdown('<div class="scroll-container">', unsafe_allow_html=True)
        for i, bin_data in enumerate(all_bins):
            st.markdown(f"**板材序號: {i+1}**")
            # 這裡調用上面的 draw_sheet 函式
            sheet_img = draw_sheet(bin_data, sw, sh, scale=0.3)
            st.image(sheet_img, use_container_width=True)
            st.markdown("---")
        st.markdown('</div>', unsafe_allow_html=True)

        # --- 底部精準估價 ---
        st.divider()
        st.subheader("💰 總預算估計")
        cc1, cc2, cc3 = st.columns(3)
        cc1.write(f"板材費用: **${int(num_sheets * board_price)}**")
        cc2.write(f"貼皮成本: **${int(skin_total_cost)}**")
        cc3.write(f"**總計金額: ${int(total_final_price)}**")
    else:
        st.info("請輸入清單數據以生成預覽。")