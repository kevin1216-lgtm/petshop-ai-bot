import streamlit as st
import sqlite3
import pandas as pd
import glob
import re
from langchain_google_genai import ChatGoogleGenerativeAI

# ==========================================
# 1. 系統環境與版面設定
# ==========================================
st.set_page_config(
    page_title="寵物店AI智慧查詢系統", 
    page_icon="🐾", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# 隱藏 Streamlit 預設的右上角選單與底部浮水印 (打造正式產品感)
hide_st_style = """
            <style>
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            header {visibility: hidden;}
            </style>
            """
st.markdown(hide_st_style, unsafe_allow_html=True)

st.title("🐾 寵物店 AI 智慧查詢系統")
st.caption("⚡ Hybrid Engine v1.0：本機極速規則 × Google Gemini AI 混合處理架構")

# --- 尋找本地端資料庫檔案 ---
db_files = glob.glob('*.db') + glob.glob('*.sqlite')
default_index = db_files.index("petshop_full.db") if "petshop_full.db" in db_files else 0

# ==========================================
# 2. 側邊欄控制中心 (UI/UX 拋光)
# ==========================================
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/2809/2809827.png", width=80) # 裝飾用 Icon
    st.header("系統控制中心")
    
    st.markdown("### 🗄️ 資料來源設定")
    selected_db = st.selectbox("請選擇資料庫檔案", db_files, index=default_index, label_visibility="collapsed")
    
    st.markdown("### 🧠 AI 大腦擴充 (選填)")
    api_key_input = st.text_input("Google Gemini API Key", type="password", placeholder="輸入金鑰解鎖進階問題...", label_visibility="collapsed")
    
    if api_key_input:
        st.success("✅ AI 引擎已解鎖，支援自然語言問答！")
    else:
        st.info("💡 目前為【極速本機模式】。輸入金鑰可啟用 AI 跨表分析功能。")
    
    with st.expander("📖 系統使用指南 (點擊展開)", expanded=False):
        st.markdown("""
        **【極速本機模式】 (無需 API)**
        支援瞬間查詢，請輸入關鍵字：
        - `員工`：列出所有員工
        - `會員` 或 `會員 M001`：查詢會員
        - `商品` 或 `商品類別`：查庫存與分類
        - `美容` 或 `美容項目`：查美容紀錄/價目
        - `醫療` 或 `醫療項目`：查看診紀錄/價目
        - `住宿` 或 `旅舍`：查住宿紀錄/價目
        - `銷售` 或 `訂單`：查結帳紀錄
        - *支援電話反查 (例：0910001003)*
        
        **【AI 智能模式】 (需填寫 API Key)**
        支援複雜查詢與跨表問答：
        - *「幫我算出上個月的總營收」*
        - *「狗狗一直抓癢可能是什麼原因？」*
        """)

    # --- 版本版權宣告 ---
    st.markdown("---")
    st.markdown(
        """
        <div style='text-align: center; margin-top: 20px; font-size: 12px; color: gray;'>
            <strong>寵物店智慧查詢系統 v1.0</strong><br>
            © 2026 PetShop Platform.<br>
            Powered by Streamlit & Gemini
        </div>
        """, 
        unsafe_allow_html=True
    )

# ==========================================
# 3. 資料庫連線與快取 (Caching)
# ==========================================
@st.cache_data(ttl=600) # 快取 10 分鐘，降低資料庫讀取負擔
def execute_sql(db_path, query):
    conn = sqlite3.connect(db_path)
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

# ==========================================
# 4. 核心邏輯：混合路由 (Hybrid Routing)
# ==========================================
def smart_query(user_query, db_path, api_key):
    if not db_path:
        return None, "⚠️ 請先從左側系統控制中心選擇資料庫檔案！"
    
    clean_query = user_query.lower().replace(" ", "")

    # ----------------------------------------
    # 引擎 1：本機極速規則 (Regex + SQL Join)
    # ----------------------------------------
    query = None
    msg = ""
    
    # 擷取特徵 (會員ID, 員工ID, 電話)
    m_id_match = re.search(r'(m\d{3})', clean_query)
    e_id_match = re.search(r'(e\d{3})', clean_query)
    phone_match = re.search(r'(09\d{2})-?(\d{3})-?(\d{3})', clean_query)
    is_item_query = any(keyword in clean_query for keyword in ["項目", "種類", "清單", "有哪些", "甚麼", "什麼"])

    # 判斷查詢意圖
    if phone_match:
        formatted_phone = f"{phone_match.group(1)}-{phone_match.group(2)}-{phone_match.group(3)}"
        query = f"""
        SELECT m.會員姓名, m.電話, m.會員等級, p.寵物名稱, p.品種, p.出生日期
        FROM Member m
        LEFT JOIN Pet p ON m."會員ID*" = p.會員ID
        WHERE m.電話 = '{formatted_phone}'
        """
        msg = f"📞 透過電話 ({formatted_phone}) 找到以下結果 (極速引擎)："
        
    elif "員工" in clean_query:
        if e_id_match:
            e_id = e_id_match.group(1).upper()
            query = f'SELECT e."員工ID*", d.部門名稱, e.員工姓名, e.職稱, e.電話, e.狀態 FROM Employee e LEFT JOIN Department d ON e.部門ID = d."部門ID*" WHERE e."員工ID*" = \'{e_id}\''
            msg = f"🧑‍💼 員工 {e_id} 專屬資料 (極速引擎)："
        else:
            query = 'SELECT e."員工ID*", d.部門名稱, e.員工姓名, e.職稱, e.電話, e.狀態 FROM Employee e LEFT JOIN Department d ON e.部門ID = d."部門ID*"'
            msg = "🧑‍💼 店內全體員工名單 (極速引擎)："
            
    elif "會員" in clean_query:
        if m_id_match:
            m_id = m_id_match.group(1).upper()
            query = f'SELECT m."會員ID*", m.會員姓名, m.電話, m.會員等級, p.寵物名稱, p.品種 FROM Member m LEFT JOIN Pet p ON m."會員ID*" = p.會員ID WHERE m."會員ID*" = \'{m_id}\''
            msg = f"👑 會員 {m_id} 及其寵物資料 (極速引擎)："
        else:
            query = "SELECT * FROM Member"
            msg = "👑 全體會員清單 (極速引擎)："
            
    elif "商品" in clean_query or "庫存" in clean_query:
        if is_item_query and "類" in clean_query:
            query = "SELECT * FROM Product_Class"
            msg = "📦 店內商品類別清單 (極速引擎)："
        else:
            query = 'SELECT i."商品ID*", c.商品類別名稱, i.商品名稱, i.售價, i.庫存量, i.品牌 FROM Product_Item i LEFT JOIN Product_Class c ON i.商品類別ID = c."商品類別ID*"'
            msg = "📦 目前店內商品與庫存狀況 (極速引擎)："
        
    elif "美容" in clean_query:
        if m_id_match:
            m_id = m_id_match.group(1).upper()
            query = f'SELECT r.美容日期, m.會員姓名, p.寵物名稱, e.員工姓名 AS 美容師, r.美容項目, r.總金額, r.狀態 FROM Grooming_Record r LEFT JOIN Member m ON r.會員ID = m."會員ID*" LEFT JOIN Pet p ON r.寵物ID = p."寵物ID*" LEFT JOIN Employee e ON r.員工ID = e."員工ID*" WHERE r.會員ID = \'{m_id}\''
            msg = f"✂️ 會員 {m_id} 的美容紀錄 (極速引擎)："
        elif is_item_query:
            query = "SELECT 美容項目名稱, 適用寵物, 費用, 說明 FROM Grooming_Item"
            msg = "✂️ 店內提供的美容項目清單 (極速引擎)："
        else:
            query = 'SELECT r.美容日期, m.會員姓名, p.寵物名稱, e.員工姓名 AS 美容師, r.美容項目, r.總金額, r.狀態 FROM Grooming_Record r LEFT JOIN Member m ON r.會員ID = m."會員ID*" LEFT JOIN Pet p ON r.寵物ID = p."寵物ID*" LEFT JOIN Employee e ON r.員工ID = e."員工ID*" ORDER BY r.美容日期 DESC'
            msg = "✂️ 近期美容服務紀錄 (極速引擎)："
            
    elif "醫療" in clean_query:
        if m_id_match:
            m_id = m_id_match.group(1).upper()
            query = f'SELECT r.看診日期, m.會員姓名, p.寵物名稱, e.員工姓名 AS 看診醫師, r.醫療項目, r.診斷原因, r.總金額, r.備註 FROM Medical_Record r LEFT JOIN Member m ON r.會員ID = m."會員ID*" LEFT JOIN Pet p ON r.寵物ID = p."寵物ID*" LEFT JOIN Employee e ON r.員工ID = e."員工ID*" WHERE r.會員ID = \'{m_id}\''
            msg = f"🏥 會員 {m_id} 的醫療紀錄 (極速引擎)："
        elif is_item_query:
            query = "SELECT 醫療項目名稱, 適用寵物, 費用, 說明 FROM Medical_Item"
            msg = "🏥 店內提供的醫療項目清單 (極速引擎)："
        else:
            query = 'SELECT r.看診日期, m.會員姓名, p.寵物名稱, e.員工姓名 AS 看診醫師, r.醫療項目, r.診斷原因, r.總金額, r.備註 FROM Medical_Record r LEFT JOIN Member m ON r.會員ID = m."會員ID*" LEFT JOIN Pet p ON r.寵物ID = p."寵物ID*" LEFT JOIN Employee e ON r.員工ID = e."員工ID*" ORDER BY r.看診日期 DESC'
            msg = "🏥 近期醫療看診紀錄 (極速引擎)："

    elif "住宿" in clean_query or "旅舍" in clean_query:
        if m_id_match:
            m_id = m_id_match.group(1).upper()
            query = f'SELECT r.入住日期, r.退房日期, m.會員姓名, p.寵物名稱, e.員工姓名 AS 負責員工, r.旅舍項目, r.住宿天數, r.總金額, r.狀態 FROM Hotel_Record r LEFT JOIN Member m ON r.會員ID = m."會員ID*" LEFT JOIN Pet p ON r.寵物ID = p."寵物ID*" LEFT JOIN Employee e ON r.員工ID = e."員工ID*" WHERE r.會員ID = \'{m_id}\''
            msg = f"🏠 會員 {m_id} 的住宿紀錄 (極速引擎)："
        elif is_item_query:
            query = "SELECT 旅舍項目名稱, 適用寵物, 每日費用, 說明 FROM Hotel_Item"
            msg = "🏠 店內提供的寵物住宿項目清單 (極速引擎)："
        else:
            query = 'SELECT r.入住日期, r.退房日期, m.會員姓名, p.寵物名稱, e.員工姓名 AS 負責員工, r.旅舍項目, r.住宿天數, r.總金額, r.狀態 FROM Hotel_Record r LEFT JOIN Member m ON r.會員ID = m."會員ID*" LEFT JOIN Pet p ON r.寵物ID = p."寵物ID*" LEFT JOIN Employee e ON r.員工ID = e."員工ID*" ORDER BY r.入住日期 DESC'
            msg = "🏠 近期寵物住宿紀錄 (極速引擎)："
            
    elif "銷售" in clean_query or "訂單" in clean_query or "結帳" in clean_query:
        if m_id_match:
            m_id = m_id_match.group(1).upper()
            query = f'SELECT r.銷售日期, m.會員姓名, e.員工姓名 AS 銷售員, i.商品名稱, r.數量, r.單價, r.實收金額 FROM Sales_Record r LEFT JOIN Member m ON r.會員ID = m."會員ID*" LEFT JOIN Employee e ON r.員工ID = e."員工ID*" LEFT JOIN Product_Item i ON r.商品ID = i."商品ID*" WHERE r.會員ID = \'{m_id}\''
            msg = f"💰 會員 {m_id} 的消費結帳紀錄 (極速引擎)："
        else:
            query = 'SELECT r.銷售日期, m.會員姓名, e.員工姓名 AS 銷售員, i.商品名稱, r.數量, r.單價, r.實收金額 FROM Sales_Record r LEFT JOIN Member m ON r.會員ID = m."會員ID*" LEFT JOIN Employee e ON r.員工ID = e."員工ID*" LEFT JOIN Product_Item i ON r.商品ID = i."商品ID*" ORDER BY r.銷售日期 DESC'
            msg = "💰 近期商品銷售結帳紀錄 (極速引擎)："

    # 若命中本機引擎，直接回傳結果，0 延遲且免 API 額度
    if query:
        try:
            df = execute_sql(db_path, query)
            if df.empty:
                 return None, "⚠️ 資料庫中查無此條件的相關紀錄喔！"
            return df, msg
        except Exception as e:
            return None, f"⚠️ 系統查詢發生錯誤：\n{e}"

    # ----------------------------------------
    # 引擎 2：Gemini AI 智能大腦 (處理未知與複雜意圖)
    # ----------------------------------------
    if not api_key:
        return None, "🤖 **提示：本機規則庫未能識別此問題。**\n\n這似乎是一個需要跨表分析或不包含在預設關鍵字中的複雜問題。若需解開此問題，請在左側面板輸入您的 `Gemini API Key` 喚醒 AI 大腦！\n\n*(或者您也可以嘗試更明確的關鍵字，例如：「會員 M001」或「電話 0910001003」)*"

    try:
        llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0, google_api_key=api_key)
        
        schema_info = """
        【基本檔資料表】
        - Department: "部門ID*", "部門名稱", "部門說明"
        - Employee: "員工ID*", "部門ID", "員工姓名", "職稱", "性別", "電話", "Email", "到職日期", "狀態"
        - Member: "會員ID*", "會員姓名", "性別", "電話", "Email", "地址", "加入日期", "會員等級"
        - Pet: "寵物ID*", "會員ID", "寵物名稱", "寵物類型", "品種", "性別", "出生日期", "體重KG", "結紮狀態", "備註"
        【營業部門資料表】
        - Product_Class: "商品類別ID*", "商品類別名稱", "類別說明"
        - Product_Item: "商品ID*", "商品類別ID", "商品名稱", "適用寵物", "單位", "售價", "庫存量", "品牌"
        - Sales_Record: "銷售ID*", "銷售日期", "會員ID", "員工ID", "商品ID", "數量", "單價", "小計", "折扣金額", "實收金額", "付款方式", "備註"
        - Medical_Item: "醫療ID*", "醫療類別ID", "醫療項目名稱", "適用寵物", "費用", "說明"
        - Medical_Record: "醫療紀錄ID*", "看診日期", "會員ID", "寵物ID", "員工ID", "醫療ID", "醫療項目", "診斷原因", "醫療費", "藥品費", "總金額", "備註"
        - Grooming_Item: "美容項目ID*", "美容類別ID", "美容項目名稱", "適用寵物", "費用", "說明"
        - Grooming_Record: "美容紀錄ID*", "美容日期", "會員ID", "寵物ID", "員工ID", "美容項目ID", "美容項目", "基本費用", "加購費用", "總金額", "狀態", "備註"
        - Hotel_Item: "旅舍項目ID*", "旅舍類別ID", "旅舍項目名稱", "適用寵物", "每日費用", "說明"
        - Hotel_Record: "旅舍紀錄ID*", "會員ID", "寵物ID", "員工ID", "旅舍項目ID", "旅舍項目", "入住日期", "退房日期", "住宿天數", "每日費用", "加購費用", "總金額", "狀態", "備註"
        【限制】主鍵(帶星號)需加雙引號，例：Member."會員ID*"
        """
        
        routing_prompt = f"""
        請判斷以下使用者的輸入：
        如果是在詢問寵物店的內部統計或跨表分析資料，請根據提供的資料表結構，輸出純 SQL 語法 (不要加上 ```sql 等標記)。
        如果是一般的寵物知識問答、打招呼、或與系統無關的閒聊，請直接用親切的口吻回答，並在回覆最前方加上「CHAT:」。
        
        資料庫結構：{schema_info}
        使用者輸入：{user_query}
        """
        
        ai_response = llm.invoke(routing_prompt).content.strip()
        
        if ai_response.startswith("CHAT:"):
            return None, ai_response.replace("CHAT:", "").strip()
        else:
            sql_query = ai_response.replace("```sql", "").replace("```", "").strip()
            df = execute_sql(db_path, sql_query)
            if df.empty:
                return None, "🤖 **AI 分析完畢：** 但在資料庫中並未找到符合此條件的紀錄喔！"
            
            return df, f"🤖 **AI 智能生成結果：** (已自動轉換複雜語義)"
            
    except Exception as e:
        error_msg = str(e).lower()
        if "429" in error_msg or "quota" in error_msg:
            return None, "⏳ **API 流量管制中：** AI 大腦的配額已暫時耗盡。請稍後再試，或使用內建關鍵字觸發極速本機查詢！"
        return None, f"⚠️ AI 處理時發生異常：\n{e}"

# ==========================================
# 5. 聊天介面渲染區
# ==========================================
if "messages" not in st.session_state:
    welcome_msg = (
        "您好！歡迎使用 **🐾寵物店混合雙引擎助理**。\n\n"
        "✨ **零延遲查詢 (免 API)**：直接輸入「`會員清單`」、「`電話 0910001003`」、「`員工資料`」、「`醫療有哪些項目`」等關鍵字。\n"
        "✨ **AI 智能問答 (需金鑰)**：輸入您的 API Key 後，可詢問更複雜的問題或一般的寵物健康知識！\n\n"
        "*請在下方輸入列開始查詢：*"
    )
    st.session_state.messages = [{"role": "assistant", "content": welcome_msg}]
    st.toast('系統初始化成功！', icon='🚀') # 第一次載入顯示提示框

# 顯示歷史訊息
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        if "dataframe" in msg and msg["dataframe"] is not None:
            st.dataframe(msg["dataframe"], use_container_width=True)
        st.markdown(msg["content"])

# 處理使用者輸入
if prompt := st.chat_input("輸入查詢關鍵字 (例：美容紀錄) 或寵物問題..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("系統處理中，請稍候..."):
            df_result, text_response = smart_query(prompt, selected_db, api_key_input)
            
            if df_result is not None:
                st.dataframe(df_result, use_container_width=True)
            st.markdown(text_response)
        
    st.session_state.messages.append({"role": "assistant", "content": text_response, "dataframe": df_result})

    # 若有人輸入特定的慶祝關鍵字，觸發彩蛋
    if "辛苦了" in prompt or "謝謝" in prompt:
        st.balloons()
