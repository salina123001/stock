import requests
import pandas as pd
import google.generativeai as genai
from dotenv import load_dotenv
import os
import random
import string
import streamlit as st
import sys

# 設定頁面配置
st.set_page_config(
    page_title="台股AI分析工具",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 在 PythonAnywhere 上，我們直接設定環境變數而不是使用 .env 檔案
# 如果 .env 檔案存在，則嘗試載入
try:
    load_dotenv("test.env")
except:
    pass

# 從環境變數或直接設定 API 金鑰
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    # 如果在 PythonAnywhere 上，你可能想要直接在這裡設定 API 金鑰
    # GEMINI_API_KEY = "你的API金鑰"
    st.error("找不到 Gemini API 金鑰，請確保已設定環境變數 GEMINI_API_KEY")
    st.stop()

genai.configure(api_key=GEMINI_API_KEY)

# API URLs
api_urls = {
    "roe": "https://openapi.twse.com.tw/v1/exchangeReport/BWIBBU_ALL",
    "stock_price": "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_AVG_ALL",
    "finance": "https://openapi.twse.com.tw/v1/opendata/t187ap06_L_ci"
}

# 需要的財報欄位
required_columns = {
    "公司代號": "股票代號",
    "年度": "財報年度",
    "季別": "財報季度",
    "營業收入": "營業額",
    "營業毛利": "營業毛利",
    "營業利益": "營業利益",
    "稅後淨利": "稅後淨利",
    "基本每股盈餘": "EPS",
    "股東權益報酬率": "ROE",
    "PEratio": "本益比",
    "DividendYield": "殖利率",
    "PBratio": "股價淨值比",
    "ClosingPrice": "收盤價",
    "MonthlyAveragePrice": "月均價"
}

@st.cache_data(ttl=3600)  # 快取資料1小時
def fetch_data(stock_id):
    """擷取財務數據並存入 DataFrame"""
    data_frames = {}

    for key in api_urls:
        try:
            response = requests.get(api_urls[key])
            if response.status_code == 200:
                df = pd.DataFrame(response.json())

                if "公司代號" in df.columns:
                    df.rename(columns={"公司代號": "股票代號"}, inplace=True)
                
                if "Code" in df.columns:
                    df.rename(columns={"Code": "股票代號"}, inplace=True)

                df.rename(columns=required_columns, inplace=True, errors='ignore')
                df = df[df["股票代號"].astype(str) == stock_id]

                if not df.empty:
                    data_frames[key] = df

        except Exception as e:
            st.error(f"擷取 {key} 資料時發生錯誤: {e}")

    return data_frames

def merge_data(data_frames):
    """合併財務數據"""
    if not data_frames:
        return pd.DataFrame()

    # 確保 "股票代號" 欄位為字串，避免合併失敗
    for key in data_frames:
        if "股票代號" in data_frames[key].columns:
            data_frames[key]["股票代號"] = data_frames[key]["股票代號"].astype(str)

    # 從第一個資料框開始合併
    merged_df = next(iter(data_frames.values()))
    
    # 合併其餘的資料框
    for key, df in data_frames.items():
        if df is not merged_df:  # 避免合併自己
            merged_df = merged_df.merge(df, on="股票代號", how="outer")

    # 處理欄位名稱重複問題
    name_columns = [col for col in merged_df.columns if col.startswith('Name')]
    if len(name_columns) > 0:
        # 保留第一個 Name 欄位作為公司名稱
        merged_df.rename(columns={name_columns[0]: "公司名稱"}, inplace=True)
        # 刪除其他 Name 欄位
        for col in name_columns[1:]:
            if col in merged_df.columns:
                merged_df.drop(columns=[col], inplace=True)
    
    # 將數值欄位轉換為數值型別，錯誤時填充 NaN
    numeric_cols = ["EPS", "ROE", "稅後淨利", "本益比", "殖利率", "股價淨值比", "收盤價", "月均價"]
    for col in numeric_cols:
        if col in merged_df.columns:
            merged_df[col] = pd.to_numeric(merged_df[col], errors='coerce')

    return merged_df

def extract_financial_data(df, stock_id):
    """從合併的數據中提取財務數據"""
    if df.empty:
        return None

    # 確保股票代號為字串類型
    df["股票代號"] = df["股票代號"].astype(str)
    stock_id = str(stock_id)
    
    # 檢查股票是否存在於數據中
    stock_data = df[df["股票代號"] == stock_id]
    if stock_data.empty:
        return None

    latest_data = stock_data.iloc[-1]
    
    # 創建一個乾淨的資料字典
    clean_data = {
        "股票代號": stock_id,
        "公司名稱": latest_data.get("公司名稱", "未知公司"),
        "營業額": 0.0,
        "稅後淨利": 0.0,
        "EPS": 0.0,
        "ROE": 0.0,
        "本益比": 0.0,
        "殖利率": 0.0,
        "股價淨值比": 0.0,
        "收盤價": 0.0,
        "月均價": 0.0
    }
    
    # 欄位映射表
    field_mappings = {
        "營業額": ["營業額", "營收"],
        "稅後淨利": ["本期淨利（淨損）", "稅後淨利", "稅後淨損", "淨利"],
        "EPS": ["基本每股盈餘（元）", "EPS", "每股盈餘"],
        "本益比": ["本益比", "P/E"],
        "殖利率": ["殖利率", "股利殖利率"],
        "股價淨值比": ["股價淨值比", "P/B", "PBR"],
        "收盤價": ["收盤價", "股價"],
        "月均價": ["月均價", "月平均價"]
    }
    
    # 處理每個欄位
    for key, possible_cols in field_mappings.items():
        for col_name in possible_cols:
            if col_name in latest_data and pd.notna(latest_data[col_name]):
                try:
                    value = latest_data[col_name]
                    # 處理字串格式的數值
                    if isinstance(value, str):
                        value = value.replace(',', '').replace('%', '')
                    clean_data[key] = float(value)
                    break  # 找到並成功轉換後跳出內部循環
                except (ValueError, TypeError):
                    pass
    
    # 計算 ROE (如果沒有直接提供)
    if clean_data["ROE"] == 0:
        try:
            if clean_data["股價淨值比"] > 0 and clean_data["收盤價"] > 0:
                book_value_per_share = clean_data["收盤價"] / clean_data["股價淨值比"]
                if book_value_per_share > 0 and clean_data["EPS"] > 0:
                    clean_data["ROE"] = round((clean_data["EPS"] / book_value_per_share) * 100, 2)
        except Exception:
            pass
    
    # 檢查數據完整性
    missing_fields = []
    for key, value in clean_data.items():
        if key not in ["股票代號", "公司名稱"] and value == 0:
            missing_fields.append(key)
    
    # 檢查資料是否有異常
    critical_fields = ["稅後淨利", "EPS", "ROE", "收盤價"]
    has_critical_errors = False
    for key in critical_fields:
        if clean_data[key] <= 0:
            has_critical_errors = True
            break
    
    clean_data["missing_fields"] = missing_fields
    clean_data["has_critical_errors"] = has_critical_errors
    
    return clean_data

def analyze_with_ai(financial_data, analysis_focus=None):
    """使用 Gemini AI 進行財務數據分析"""
    if not financial_data:
        return "無法取得此股票數據，請確認股票代號是否正確。"
    
    # 從財務數據中提取資訊
    clean_data = financial_data.copy()
    missing_fields = clean_data.pop("missing_fields")
    has_critical_errors = clean_data.pop("has_critical_errors")
    
    # 根據使用者選擇的分析重點調整提示詞
    focus_prompts = {
        "獲利": "請著重分析公司的獲利能力、ROE和EPS趨勢，評估公司的盈利品質和持續性。",
        "風險": "請詳細評估投資風險，包括估值風險、產業風險、財務風險和地緣政治風險。特別關注本益比和股價淨值比是否合理。",
        "成長": "請分析公司的成長潛力、未來發展機會和產業趨勢。評估公司的競爭優勢和市場擴張能力。",
        "股利": "請著重分析公司的股利政策、殖利率表現和股利發放穩定性。評估股利成長潛力和可持續性。",
        "積極投資": "請以積極投資者的視角分析，著重於成長機會、市場擴張潛力和可能的股價催化劑。忽略短期波動風險，專注於長期高回報可能性。提供更進取的投資建議和時機點判斷。"
    }
    
    # 設定分析重點
    focus_instruction = ""
    if analysis_focus and analysis_focus in focus_prompts:
        focus_instruction = focus_prompts[analysis_focus]
    
    # 構建 AI 解析提示詞
    market_summary = f"""
    # 財務分析請求
    
    ## 公司基本資料
    - 公司: {clean_data['公司名稱']} ({clean_data['股票代號']})
    
    ## 財務數據摘要
    - 營業額: {clean_data['營業額']:,.1f} 元
    - 稅後淨利: {clean_data['稅後淨利']:,.1f} 元
    - 每股盈餘 (EPS): {clean_data['EPS']:.1f}
    - 股東權益報酬率 (ROE): {clean_data['ROE']:.1f}%
    - 本益比 (P/E Ratio): {clean_data['本益比']:.1f}
    - 殖利率 (Dividend Yield): {clean_data['殖利率']:.1f}%
    - 股價淨值比 (P/B Ratio): {clean_data['股價淨值比']:.1f}
    - 收盤價: {clean_data['收盤價']:,.2f} 元
    - 月均價: {clean_data['月均價']:,.2f} 元
    
    {f"⚠️ 注意：以下關鍵財務數據缺失或異常: {', '.join(missing_fields)}" if missing_fields else ""}
    {f"⚠️ 警告：部分關鍵財務數據（如稅後淨利、EPS、ROE或收盤價）為零或異常，分析結果可能不準確。" if has_critical_errors else ""}
    
    ## 分析重點
    {focus_instruction if focus_instruction else "請全面分析公司財務狀況、投資價值和風險。"}
    
    ## 分析要求
    1. 請以繁體中文回覆
    2. 請提供結構化分析報告，包含以下部分：
       - 優勢分析
       - 潛在風險和需注意的點
       - 未來趨勢與投資建議
       - 總結
    3. 使用表情符號增加可讀性
    4. 如果數據存在異常或缺失，請在分析中指出並解釋可能的影響
    5. 請客觀分析，避免過度樂觀或悲觀的偏見
    """
    
    try:
        # 顯示分析中的提示
        with st.spinner('AI 正在分析財務數據，請稍候...'):
            # 直接使用指定的模型
            model_name = "models/gemini-1.5-pro-latest"
            model = genai.GenerativeModel(model_name)
            
            # 設定生成參數
            generation_config = {
                "temperature": 0.2,  # 較低的溫度使輸出更加確定性
                "top_p": 0.95,
                "top_k": 40,
                "max_output_tokens": 2048,
            }
            
            # 生成內容
            response = model.generate_content(
                market_summary,
                generation_config=generation_config
            )
            
            return response.text

    except Exception as e:
        return f"AI 分析發生錯誤: {str(e)}"

def display_welcome():
    """顯示歡迎訊息和使用說明"""
    st.title("📊 台股 AI 分析工具")
    
    st.markdown("""
    ### 👋 歡迎使用台股 AI 分析工具！

    這個工具能幫助您快速分析台灣上市公司的財務狀況，並提供 AI 生成的投資建議。

    #### 📝 使用方法：
    1. 在下方輸入框中輸入股票代號（例如：2330）
    2. 選擇您希望的分析重點
    3. 點擊「分析」按鈕
    4. 查看 AI 生成的分析報告

    #### ✨ 功能特點：
    - 自動擷取最新財務數據
    - 多種分析重點可選
    - AI 智能分析投資價值
    - 結構化報告一目了然

    #### ⚠️ 注意事項：
    - 分析結果僅供參考，不構成投資建議
    - 部分股票可能因數據缺失而無法完整分析
    - 請自行判斷投資風險
    """)

def main():
    """主函數，處理整個分析流程"""
    # 顯示歡迎訊息
    display_welcome()
    
    # 側邊欄 - 分析選項
    st.sidebar.title("分析選項")
    analysis_focus = st.sidebar.radio(
        "選擇分析重點：",
        ["全面分析", "獲利", "風險", "成長", "股利", "積極投資"],
        index=0
    )
    
    # 將選項映射到API參數
    focus_mapping = {
        "全面分析": None,
        "獲利": "獲利",
        "風險": "風險",
        "成長": "成長",
        "股利": "股利",
        "積極投資": "積極投資"
    }
    
    # 主畫面 - 股票查詢
    with st.form("stock_analysis_form"):
        stock_id = st.text_input("請輸入股票代號：", placeholder="例如：2330")
        submit_button = st.form_submit_button("分析")
    
    # 當使用者提交查詢
    if submit_button and stock_id:
        # 清除股票代號中的空白字元
        stock_id = stock_id.strip()
        
        # 顯示處理中的提示
        with st.spinner('正在擷取財務數據...'):
            # 擷取數據
            data_frames = fetch_data(stock_id)
            
            if not data_frames:
                st.error("無法取得數據，請確認股票代號是否正確。")
                return
            
            # 合併數據
            merged_df = merge_data(data_frames)
            
            if merged_df.empty:
                st.error("合併數據失敗，請確認股票代號是否正確。")
                return
            
            # 提取財務數據
            financial_data = extract_financial_data(merged_df, stock_id)
            
            if not financial_data:
                st.error("無法提取財務數據，請確認股票代號是否正確。")
                return
        
        # 顯示財務數據摘要
        st.subheader("📊 財務數據摘要")
        
        # 使用兩欄佈局顯示財務數據
        col1, col2 = st.columns(2)
        
        with col1:
            st.info(f"**公司**: {financial_data['公司名稱']} ({financial_data['股票代號']})")
            st.metric("營業額", f"{financial_data['營業額']:,.1f} 元")
            st.metric("稅後淨利", f"{financial_data['稅後淨利']:,.1f} 元")
            st.metric("每股盈餘 (EPS)", f"{financial_data['EPS']:.1f}")
            st.metric("股東權益報酬率 (ROE)", f"{financial_data['ROE']:.1f}%")
        
        with col2:
            st.metric("本益比 (P/E Ratio)", f"{financial_data['本益比']:.1f}")
            st.metric("殖利率 (Dividend Yield)", f"{financial_data['殖利率']:.1f}%")
            st.metric("股價淨值比 (P/B Ratio)", f"{financial_data['股價淨值比']:.1f}")
            st.metric("收盤價", f"{financial_data['收盤價']:,.2f} 元")
            st.metric("月均價", f"{financial_data['月均價']:,.2f} 元")
        
        # 顯示警告訊息（如果有）
        if financial_data["missing_fields"]:
            st.warning(f"⚠️ 注意：以下關鍵財務數據缺失或異常: {', '.join(financial_data['missing_fields'])}")
        
        if financial_data["has_critical_errors"]:
            st.error("⚠️ 警告：部分關鍵財務數據（如稅後淨利、EPS、ROE或收盤價）為零或異常，分析結果可能不準確。")
        
        # 執行 AI 分析
        analysis_result = analyze_with_ai(financial_data, focus_mapping[analysis_focus])
        
        # 顯示分析結果
        st.subheader("📝 AI 分析報告")
        st.markdown(analysis_result)
        
        # 提供下載數據的選項
        csv = merged_df.to_csv(index=False)
        st.download_button(
            label="下載財務數據 (CSV)",
            data=csv,
            file_name=f"stock_analysis_{stock_id}.csv",
            mime="text/csv",
        )
    
    # 顯示頁腳
    st.markdown("---")
    st.markdown("### 📌 提示")
    st.info("您可以隨時輸入新的股票代號進行分析。關閉瀏覽器視窗即可結束使用。")
    st.markdown("© 2025 台股 AI 分析工具 | 資料來源: 台灣證券交易所")

if __name__ == "__main__":
    main()
