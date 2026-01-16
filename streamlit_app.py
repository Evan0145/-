import streamlit as st
import pandas as pd
from PIL import Image, ImageDraw
from rectpack import newPacker

# 設定頁面
st.set_page_config(page_title="AI 家具生產系統 Pro", layout="wide")

# --- 1. 增添模板選項 (在此擴充功能 4) ---
PRODUCT_TEMPLATES = {
    "標準地櫃": [
        {"名稱": "側板", "寬W": 550, "高H": 800, "數量": 2, "封邊": "長邊x2"},
        {"名稱": "底板", "寬W": 550, "高H": 764, "數量": 1, "封邊": "長邊x1"},
        {"名稱": "活動層板", "寬W": 530, "高H": 760, "數量": 2, "封邊": "長邊x1"}
    ],
    "標準衣櫃": [
        {"名稱": "側板", "寬W": 600, "高H": 2400, "數量": 2, "封邊": "長邊x2"},
        {"名稱": "頂底板", "寬W": 600, "高H": 800, "數量": 2, "封邊": "長邊x1"},
        {"名稱": "背板", "寬W": 800, "高H": 2300, "數量": 1, "封邊": "不封邊"}
    ],
    "三層抽屜櫃": [
        {"名稱": "抽頭板", "寬W": 150, "高H": 400, "數量": 3, "封邊": "全封"},
        {"名稱": "抽牆側", "寬W": 120, "高H": 450, "數量": 6, "封邊": "不封邊"},
        {"名稱": "抽牆前", "寬W": 120, "高H": 350, "數量": 6, "封邊": "不封邊"}
    ],
    "開放書架": [
        {"名稱": "側板", "寬W": 300, "高H": 1800, "數量": 2, "封邊": "長邊x2"},
        {"名稱": "層板", "寬W": 280, "高H": 600, "數量": 5, "封邊": "長邊x1"}
    ]
}

# --- 2. 側邊欄設定 ---
with st.sidebar:
    st.markdown("## ⚙️ 系統設定")
    st.markdown("### 📦 板材設定")
    wood_skin = st.selectbox("板材貼皮/顏色", ["白橡木", "胡桃木", "純白", "灰色", "黑木紋"])
    sw = st.number_input("板材寬度 W (mm)", value=2440)
    sh = st.number_input("板材高度 H (mm)", value=1220)
    
    st.markdown("---")
    st.markdown("### 💰 成本參數")
    board_price = st.number_input("板材單價 (元/片)", value=1500)
    skin_cost_m2 = st.number_input("貼皮加價 (元/m²)", value=200)
    kerf = st.slider("鋸路損耗 (mm)", 0, 10, 3)
    allow_rot = st.checkbox("允許旋轉零件", value=True)

# --- 3. 核心數據管理 (分櫃位管理) ---
if 'cabinets' not in st.session_state:
    # 預設兩個櫃位
    st.session_state.cabinets = {
        "物件 A": [{"名稱": "零件1", "寬W": 400, "高H": 800, "數量": 2, "封邊": "不封邊"}],
        "物件 B": []
    }

st.title("🖥️ 多物件綜合生產系統")

col_mgmt, col_preview = st.columns([1, 1.2])

with col_mgmt:
    st.subheader("🛠️ 零件管理 (按物件分組)")
    
    # 動態物件增減
    new_cab_name = st.text_input("新增物件名稱", placeholder="例如：主臥衣櫃")
    if st.button("➕ 建立新物件表格"):
        if new_cab_name and new_cab_name not in st.session_state.cabinets:
            st.session_state.cabinets[new_cab_name] = []
            st.rerun()

    # 使用分頁顯示不同表格
    if st.session_state.cabinets:
        tabs = st.tabs(list(st.session_state.cabinets.keys()))
        
        for i, (name, parts) in enumerate(st.session_state.cabinets.items()):
            with tabs[i]:
                # 模板併入選項 (功能點：不同表格獨立併入)
                c1, c2 = st.columns([2, 1])
                with c1:
                    tpl = st.selectbox(f"選擇模板加入至 {name}", list(PRODUCT_TEMPLATES.keys()), key=f"tpl_{name}")
                with c2:
                    if st.button("📥 載入模板", key=f"btn_{name}"):
                        st.session_state.cabinets[name].extend(PRODUCT_TEMPLATES[tpl])
                        st.rerun()
                
                # 數據編輯
                edited_df = st.data_editor(
                    st.session_state.cabinets[name],
                    num_rows="dynamic",
                    use_container_width=True,
                    key=f"editor_{name}"
                )
                st.session_state.cabinets[name] = edited_df
                
                if st.button(f"🗑️ 刪除整個 {name}", key=f"del_{name}"):
                    del st.session_state.cabinets[name]
                    st.rerun()

# --- 4. 綜合運算核心 ---
def run_all_packing():
    packer = newPacker(rotation=allow_rot)
    packer.add_bin(sw, sh, count=100)
    
    total_parts_area = 0
    # 彙整所有表格的零件
    for name, parts in st.session_state.cabinets.items():
        for row in parts:
            try:
                w, h, q = float(row['寬W']), float(row['高H']), int(row['數量'])
                if q > 0:
                    for _ in range(q):
                        # 標籤加上物件名稱，方便辨識
                        packer.add_rect(w + kerf, h + kerf, rid=(f"{name}-{row['名稱']}", row.get('封邊','不封邊')))
                        total_parts_area += (w * h)
            except: continue
    
    packer.pack()
    all_bins = []
    for b in packer:
        if len(b) > 0:
            rects = [{"x":r.x, "y":r.y, "w":r.width-kerf, "h":r.height-kerf, "name":r.rid[0], "edge":r.rid[1]} for r in b]
            all_bins.append({"rects": rects})
    return all_bins, total_parts_area

# --- 5. 右側：綜合預覽圖與報價 ---
with col_preview:
    all_bins, parts_area = run_all_packing()
    
    if all_bins:
        num_sheets = len(all_bins)
        usage_rate = (parts_area / (sw * sh * num_sheets)) * 100
        unused_rate = 100 - usage_rate
        
        st.subheader("📊 綜合資源分析 (彙整所有物件)")
        st.progress(usage_rate / 100)
        m1, m2, m3 = st.columns(3)
        m1.metric("總使用率", f"{usage_rate:.1f}%")
        m2.metric("總未使用率", f"{unused_rate:.1f}%")
        m3.metric("需用板材", f"{num_sheets} 片")

        # 繪圖配色
        skin_colors = {"白橡木": "#D2B48C", "胡桃木": "#5D4037", "純白": "#F5F5F5", "灰色": "#9E9E9E", "黑木紋": "#212121"}
        active_color = skin_colors[wood_skin]
        t_color = "white" if wood_skin in ["胡桃木", "黑木紋"] else "black"

        st.markdown('<div style="max-height: 60vh; overflow-y: auto; border: 1px solid #EEE; padding: 10px;">', unsafe_allow_html=True)
        for i, bin_data in enumerate(all_bins):
            st.write(f"**第 {i+1} 片裁切配置**")
            # 這裡簡單畫圖 (scale 稍微縮小以適應介面)
            scale = 0.3
            img = Image.new('RGB', (int(sw*scale)+40, int(sh*scale)+40), "#FFFFFF")
            draw = ImageDraw.Draw(img)
            draw.rectangle([20, 20, 20+sw*scale, 20+sh*scale], outline="#333", width=2)
            for r in bin_data['rects']:
                x1, y1, x2, y2 = 20+r['x']*scale, 20+r['y']*scale, 20+(r['x']+r['w'])*scale, 20+(r['y']+r['h'])*scale
                draw.rectangle([x1, y1, x2, y2], fill=active_color, outline="black")
                if r['w']*scale > 40: draw.text((x1+2, y1+2), r['name'][:10], fill=t_color)
            st.image(img, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

        # 估價
        st.divider()
        st.subheader("💰 綜合預算")
        skin_cost = (parts_area / 1000000) * skin_cost_m2
        total = (num_sheets * board_price) + skin_cost
        c1, c2, c3 = st.columns(3)
        c1.write(f"板材費: **${int(num_sheets*board_price)}**")
        c2.write(f"貼皮費: **${int(skin_cost)}**")
        c3.write(f"**總預算: ${int(total)}**")
    else:
        st.info("請在左側物件表格中輸入數據或載入模板。")