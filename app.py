import streamlit as st
import requests
import json
import re
import time
import pandas as pd

# ================= 1. 页面配置 =================
st.set_page_config(
    page_title="个人专属基金看板",
    page_icon="💰",
    layout="wide"
)

# ================= 2. 核心数据获取 (直连版) =================
def get_fund_realtime_data(code):
    timestamp = int(time.time() * 1000)
    url = f"http://fundgz.1234567.com.cn/js/{code}.js?rt={timestamp}"
    
    try:
        response = requests.get(url, timeout=2)
        if response.status_code == 200:
            match = re.search(r'jsonpgz\((.*?)\);', response.text)
            if match:
                return json.loads(match.group(1))
    except:
        pass
    return None

# ================= 3. 侧边栏：持仓配置 =================
with st.sidebar:
    st.header("📝 持仓配置")
    
    # --- 修改点提示 ---
    st.info("格式：基金代码, 当前持有金额 (每行一个)")
    st.caption("提示：请输入昨晚更新后的【最新市值】或你的【本金】，系统将基于此金额计算今日盈亏。")
    
    # 默认值 (改为金额示例)
    default_input = """110011, 10000
005827, 20000
000001, 5000"""
    
    user_input = st.text_area("在此输入", value=default_input, height=250)
    
    # 刷新按钮
    if st.button("🔄 刷新数据", type="primary"):
        st.rerun()

# ================= 4. 主界面逻辑 =================

st.title("📈 个人专属基金看板")
st.caption("🚀 **极速版 (金额模式)**：直接输入持有金额，自动计算今日盈亏。")

# --- 数据处理 ---
holdings = []
lines = user_input.strip().split('\n')
for line in lines:
    parts = line.replace('，', ',').split(',')
    if len(parts) >= 2:
        c = parts[0].strip()
        # 这里把输入的第二项解析为“金额 (Amount)”
        try:
            a = float(parts[1].strip())
            if c and a: holdings.append((c, a))
        except:
            pass

results = []
total_profit = 0      # 总预估盈亏
total_asset = 0       # 总最新市值

# 循环获取数据
if holdings:
    progress_bar = st.progress(0)
    
    for i, (code, amount) in enumerate(holdings):
        progress_bar.progress((i + 1) / len(holdings))
        data = get_fund_realtime_data(code)
        
        if data:
            name = data['name']
            gszzl = float(data['gszzl'])  # 估算涨跌幅 (例如 1.5 代表 1.5%)
            time_str = data['gztime']     # 更新时间
            
            # --- 核心计算逻辑修改 ---
            # 盈亏 = 持有金额 * (涨跌幅 / 100)
            profit = amount * (gszzl / 100)
            
            # 最新市值 = 原有金额 + 今日盈亏
            # (注意：这里的 amount 如果是昨天的市值，那么 current_val 就是今天的实时市值)
            current_val = amount + profit
            
            total_profit += profit
            total_asset += current_val
            
            results.append({
                "基金名称": name,
                "代码": code,
                "估算涨幅": gszzl,
                "预估盈亏": profit,
                "持有金额(昨)": amount,   # 显示原本输入的金额
                "最新市值(今)": current_val, # 显示加上盈亏后的金额
                "更新时间": time_str
            })
        else:
             results.append({
                 "基金名称": "获取失败", "代码": code, 
                 "估算涨幅":0, "预估盈亏":0, 
                 "持有金额(昨)": amount, "最新市值(今)": amount, 
                 "更新时间": "--"
             })

    progress_bar.empty()

# --- 界面展示 ---

# 1. 顶部大指标
col1, col2 = st.columns(2)
with col1:
    st.metric("今日预估总盈亏", f"{total_profit:+.2f} 元", delta=f"{total_profit:+.2f}")
with col2:
    st.metric("实时持有总市值", f"{total_asset:,.2f} 元")

st.divider()

# 2. 详细表格
if results:
    df = pd.DataFrame(results)
    
    # 颜色逻辑
    def color_profit(val):
        if val > 0: return 'color: #d62728' # 红
        if val < 0: return 'color: #2ca02c' # 绿
        return 'color: black'

    # 渲染表格
    st.dataframe(
        df.style
        .format({
            "估算涨幅": "{:+.2f}%",
            "预估盈亏": "{:+.2f}",
            "持有金额(昨)": "{:,.2f}",
            "最新市值(今)": "{:,.2f}"
        })
        .map(color_profit, subset=['估算涨幅', '预估盈亏']), 
        use_container_width=True,
        hide_index=True,
        height=500
    )
    
    last_update = results[0]['更新时间'] if results else time.strftime('%Y-%m-%d %H:%M')
    st.caption(f"数据更新于: {last_update}")

else:
    st.info("👈 请在左侧输入：基金代码, 持有金额")