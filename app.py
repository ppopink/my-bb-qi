import streamlit as st
import pandas as pd
import akshare as ak
import numpy as np
import concurrent.futures
from difflib import SequenceMatcher
from datetime import datetime

# ==========================================
# 核心逻辑：序列相似度匹配
# ==========================================
def calculate_seq_similarity(target_seq, stock_seq):
    # 长度校验：如果获取的数据长度连目标的 80% 都不到，说明停牌太久或数据不足，直接放弃
    if len(stock_seq) < len(target_seq) * 0.8:
        return 0.0
    
    # 寻找最长公共子序列
    matcher = SequenceMatcher(None, target_seq, stock_seq, autojunk=False)
    match = matcher.find_longest_match(0, len(target_seq), 0, len(stock_seq))
    
    # 返回匹配比例
    return match.size / len(target_seq)

# ==========================================
# 单只股票处理任务 (已修改：接收 period 参数)
# ==========================================
def process_stock_seq(code, name, price, start_date, end_date, target_seq, k_period="daily"):
    try:
        # 【关键修改】 period 参数由外部传入，可以是 'daily' 或 'weekly'
        df = ak.stock_zh_a_hist(symbol=code, period=k_period, start_date=start_date, end_date=end_date, adjust="qfq")
        
        if df.empty: return None
        
        # 转换 1/0 序列 (红=1, 绿=0)
        # 这里把 平盘(十字星) 归为 1。如果你觉得十字星算绿，把 >= 改为 >
        df['sign'] = np.where(df['收盘'] >= df['开盘'], '1', '0')
        
        stock_seq_str = "".join(df['sign'].tolist())
        
        # 计算相似度
        score = calculate_seq_similarity(target_seq, stock_seq_str)
        
        if score > 0.85: # 相似度阈值
            return {
                '代码': code,
                '名称': name,
                '当前价': price,
                '匹配度': score,
                '股票实际序列': stock_seq_str
            }
        return None
        
    except Exception:
        return None

# ==========================================
# 主控制程序
# ==========================================
def run_manual_scan(target_seq, start_date, end_date, price_range=None, k_period="daily"):
    status = st.empty()
    bar = st.progress(0)
    
    # 显示当前正在搜索的模式
    period_name = "周线" if k_period == "weekly" else "日线"
    status.info(f"1/2 获取全市场股票名单 (当前模式: {period_name})...")
    
    try:
        df_all = ak.stock_zh_a_spot_em()
        
        if price_range:
            min_p, max_p = price_range
            df_all = df_all[(df_all['最新价'] >= min_p) & (df_all['最新价'] <= max_p)]
            st.write(f"🔍 价格筛选 ({min_p}-{max_p}元): 锁定 **{len(df_all)}** 只股票")
        else:
            df_all = df_all[df_all['最新价'] > 0]
            st.warning(f"⚠️ 全市场扫描 **{len(df_all)}** 只股票...")
            
        # 强制加入嫌疑目标
        suspect = df_all[df_all['代码'] == '002115']
        if not suspect.empty:
             df_all = pd.concat([df_all, suspect]).drop_duplicates(subset=['代码'])

    except Exception as e:
        st.error(f"列表获取失败: {e}")
        return []

    status.info(f"2/2 正在进行序列比对 ({start_date}-{end_date})...")
    
    results = []
    tasks = []
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        for _, row in df_all.iterrows():
            tasks.append(
                executor.submit(
                    process_stock_seq, 
                    row['代码'], row['名称'], row['最新价'], 
                    start_date, end_date, target_seq, k_period # 传入周期
                )
            )
            
        total = len(tasks)
        for i, future in enumerate(concurrent.futures.as_completed(tasks)):
            res = future.result()
            if res:
                results.append(res)
            if i % 50 == 0: bar.progress((i+1)/total)
            
    bar.progress(1.0)
    status.success("扫描完成！")
    
    results.sort(key=lambda x: x['匹配度'], reverse=True)
    return results[:10]

# ==========================================
# 界面 UI
# ==========================================
st.set_page_config(page_title="DNA 序列猎手", layout="wide")
st.title("🧬 股票 DNA 序列猎手 (日线/周线通用版)")

# 默认序列
default_seq = "110000000010011101110111110101001010110111100001100111011101011011"

col1, col2 = st.columns([2, 1])

with col1:
    user_seq = st.text_area("在此输入红绿序列 (红=1, 绿=0)", value=default_seq, height=150)
    
    # 【新增功能】周期选择
    st.write("---")
    st.subheader("⚙️ 周期设置")
    period_option = st.radio("请选择 K 线周期", ["日线 (Daily)", "周线 (Weekly)"], horizontal=True)
    
    # 将中文选项转换为 Akshare 接受的参数
    api_period = "weekly" if "周线" in period_option else "daily"

with col2:
    s_date = st.text_input("开始日期 (YYYYMMDD)", value="20250910")
    e_date = st.text_input("结束日期 (YYYYMMDD)", value="20251218")
    
    # 如果选择了周线，给出一个提示
    if api_period == "weekly":
        st.info("⚠️ **注意**：您选择了【周线】模式。\n\n请确保您的【日期范围】足够长。\n例如：60个字符的序列在日线模式下是3个月，但在周线模式下代表 **1年零2个月** 的走势。")
    
    st.write("---")
    use_price = st.checkbox("启用价格过滤 (提速)", value=True)
    min_p = st.number_input("最低价", value=10.0)
    max_p = st.number_input("最高价", value=15.0)

if st.button("🚀 开始全市场 DNA 匹配", type="primary"):
    clean_seq = user_seq.strip().replace("\n", "").replace(" ", "")
    
    if len(clean_seq) < 5: # 周线可能序列较短，放宽限制
        st.error("序列太短。")
    else:
        p_range = (min_p, max_p) if use_price else None
        
        matches = run_manual_scan(clean_seq, s_date, e_date, p_range, k_period=api_period)
        
        if matches:
            st.balloons()
            st.write(f"### 🏆 {period_option}序列匹配结果")
            
            for idx, m in enumerate(matches):
                score = m['匹配度'] * 100
                color = "green" if score < 90 else "red"
                st.markdown(f"#### {idx+1}. **{m['名称']}** ({m['代码']}) - 匹配度: <span style='color:{color}'>{score:.1f}%</span>", unsafe_allow_html=True)
                st.text(f"目标: {clean_seq}")
                st.text(f"实际: {m['股票实际序列']}")
                
                # 差异高亮
                if len(clean_seq) == len(m['股票实际序列']):
                    diff_view = "".join([c1 if c1==c2 else "X" for c1, c2 in zip(clean_seq, m['股票实际序列'])])
                    st.text(f"差异: {diff_view}")

                st.markdown(f"[查看详情](http://quote.eastmoney.com/{'sh' if m['代码'].startswith('6') else 'sz'}{m['代码']}.html)")
                st.divider()
        else:
            st.error("未找到匹配股票。请检查日期范围是否覆盖了足够的K线数量。")
