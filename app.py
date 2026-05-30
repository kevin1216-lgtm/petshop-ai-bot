import streamlit as st
import sqlite3
import pandas as pd
import glob
import re
from langchain_google_genai import ChatGoogleGenerativeAI

# ==========================================
# 1. 系統環境與 RWD 版面設定
# ==========================================
st.set_page_config(page_title="寵物店智慧管理與服務平台", page_icon="🐾", layout="wide")

hide_st_style = """
            <style>
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            </style>
            """
st.markdown(hide_st_style, unsafe_allow_html=True)

# 🌟 安全機制：嘗試讀取 API Key，若無則設為空字串
try:
    API_KEY = st.secrets.get("GEMINI_API_KEY", "")
except FileNotFoundError:
    API_KEY = ""

DB_PATH = "petshop_full.db"

if "role" not in st.session_state:
    st.session_state.role = None       
if "user_phone" not in st.session_state:
    st.session_state.user_phone = None 
if "messages" not in st.session_state:
    st.session_state.messages = []

# ==========================================
# 2. 側邊欄：安全驗證與權限管理中心
# ==========================================
with st.sidebar:
    st.header("🔐 身份驗證管理")
    
    if st.session_state.role is None:
        login_type = st.radio("請選擇登入身份", ["顧客會員登入", "店家員工後台"])
        
        if login_type == "顧客會員登入":
            phone_input = st.text_input("請輸入您的註冊手機號碼", placeholder="例：0910000000")
            if st.button("會員登入", use_container_width=True):
                if re.match(r'^09\d{8}$', phone_input.replace("-", "")):
                    raw_p = phone_input.replace("-", "")
                    formatted_p = f"{raw_p[:4]}-{raw_p[4:7]}-{raw_p[7:]}"
                    
                    st.session_state.role = "member"
                    st.session_state.user_phone = formatted_p
                    st.session_state.messages = [{"role": "assistant", "content": f"歡迎回來！尊貴的會員。\n您可以輸入「美容價目表」查看資訊、輸入「個人資料」或「我的紀錄」調閱檔案，或是可以直接問我寵物照顧的問題喔！"}]
                    st.rerun()
                else:
                    st.error("⚠️ 請輸入正確的 10 碼手機號碼格式！")
                    
        elif login_type == "店家員工後台":
            password_input = st.text_input("請輸入員工認證密碼", type="password")
            if st.button("員工登入", use_container_width=True):
                try:
                    correct_password = st.secrets.get("EMPLOYEE_PASSWORD", "staff999")
                except FileNotFoundError:
                    correct_password = "staff999"
                    
                if password_input == correct_password:
                    st.session_state.role = "employee"
                    st.session_state.messages = [{"role": "assistant", "content": "管理後台認證成功！系統已解鎖全域查詢權限。\n您可以輸入「員工」、「會員清單」調閱紀錄。"}]
                    st.rerun()
                else:
                    st.error("⚠️ 認證密碼錯誤！")
                    
    else:
        if st.session_state.role == "employee":
            st.success("🧑‍💼 當前權限：店家員工後台")
            st.caption("具備全域資料調閱與跨表分析權限")
        else:
            st.info(f"👑 當前權限：\n\n會員 ({st.session_state.user_phone})")
            st.caption("隱私防護生效中：嚴格限制僅能存取個人專屬紀錄")
            
        if st.button("登出系統", use_container_width=True):
            st.session_state.role = None
            st.session_state.user_phone = None
            st.session_state.messages = []
            st.rerun()

# ==========================================
# 3. 資料處理層 (本地端 SQLite 快取)
# ==========================================
@st.cache_data(ttl=600)
def execute_sql(query):
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

# ==========================================
# 4. 核心控管層：嚴格權限隔離路由
# ==========================================
def secure_query(user_query, role, user_phone):
    clean_query = user_query.lower().replace(" ", "")
    query = None
    msg = ""
    
    m_id_match = re.search(r'(m\d{3})', clean_query)
    e_id_match = re.search(r'(e\d{3})', clean_query)
    phone_match = re.search(r'(09\d{2})-?(\d{3})-?(\d{3})', clean_query)
    is_item_query = any(keyword in clean_query for keyword in ["項目", "種類", "清單", "價目", "費用", "目錄"])

    if role is None:
        return None, "🔒 系統提示：請先於左側面板選擇您的身份並完成驗證登入，才能開始查詢資料。"

    # ----------------------------------------
    # 分支 1：店家員工 (全域本機極速查詢)
    # ----------------------------------------
    if role == "employee":
        if phone_match:
            f_phone = f"{phone_match.group(1)}-{phone_match.group(2)}-{phone_match.group(3)}"
            query = f'SELECT m.會員姓名, m.電話, m.會員等級, p.寵物名稱, p.品種 FROM Member m LEFT JOIN Pet p ON m."會員ID*" = p.會員ID WHERE m.電話 = \'{f_phone}\''
            msg = f"🧑‍💼 [員工權限] 透過電話 ({f_phone}) 調閱資料："
        elif "員工" in clean_query:
            if e_id_match:
                e_id = e_id_match.group(1).upper()
                query = f'SELECT e."員工ID*", d.部門名稱, e.員工姓名, e.職稱, e.電話, e.狀態 FROM Employee e LEFT JOIN Department d ON e.部門ID = d."部門ID*" WHERE e."員工ID*" = \'{e_id}\''
                msg = f"🧑‍💼 [員工權限] 員工 {e_id} 詳細檔案："
            else:
                query = 'SELECT e."員工ID*", d.部門名稱, e.員工姓名, e.職稱, e.電話, e.狀態 FROM Employee e LEFT JOIN Department d ON e.部門ID = d."部門ID*"'
                msg = "🧑‍💼 [員工權限] 全店全體員工名單："
        elif "會員" in clean_query:
            if m_id_match:
                m_id = m_id_match.group(1).upper()
                query = f'SELECT m."會員ID*", m.會員姓名, m.電話, m.會員等級, p.寵物名稱, p.品種 FROM Member m LEFT JOIN Pet p ON m."會員ID*" = p.會員ID WHERE m."會員ID*" = \'{m_id}\''
                msg = f"🧑‍💼 [員工權限] 会員 {m_id} 及其寵物建檔資料："
            else:
                query = "SELECT * FROM Member"
                msg = "🧑‍💼 [員工權限] 全域會員名單總表："
        elif "商品" in clean_query or "庫存" in clean_query:
            query = 'SELECT i."商品ID*", c.商品類別名稱, i.商品名稱, i.售價, i.庫存量, i.品牌 FROM Product_Item i LEFT JOIN Product_Class c ON i.商品類別ID = c."商品類別ID*"'
            msg = "🧑‍💼 [員工權限] 商品與即時庫存狀況："
        elif "美容" in clean_query:
            query = 'SELECT r.美容日期, m.會員姓名, p.寵物名稱, e.員工姓名 AS 美容師, r.美容項目, r.總金額, r.狀態 FROM Grooming_Record r LEFT JOIN Member m ON r.會員ID = m."會員ID*" LEFT JOIN Pet p ON r.寵物ID = p."寵物ID*" LEFT JOIN Employee e ON r.員工ID = e."員工ID*" ORDER BY r.美容日期 DESC'
            msg = "🧑‍💼 [員工權限] 歷史美容服務總紀錄："
        elif "醫療" in clean_query:
            query = 'SELECT r.看診日期, m.會員姓名, p.寵物名稱, e.員工姓名 AS 看診醫師, r.醫療項目, r.診斷原因, r.總金額 FROM Medical_Record r LEFT JOIN Member m ON r.會員ID = m."會員ID*" LEFT JOIN Pet p ON r.寵物ID = p."寵物ID*" LEFT JOIN Employee e ON r.員工ID = e."員工ID*" ORDER BY r.看診日期 DESC'
            msg = "🧑‍💼 [員工權限] 歷史醫療看診總紀錄："
        elif "住宿" in clean_query or "旅舍" in clean_query:
            query = 'SELECT r.入住日期, r.退房日期, m.會員姓名, p.寵物名稱, r.旅舍項目, r.住宿天數, r.總金額 FROM Hotel_Record r LEFT JOIN Member m ON r.會員ID = m."會員ID*" LEFT JOIN Pet p ON r.寵物ID = p."寵物ID*" ORDER BY r.入住日期 DESC'
            msg = "🧑‍💼 [員工權限] 歷史寵物旅舍總紀錄："
        elif "銷售" in clean_query or "訂單" in clean_query:
            query = 'SELECT r.銷售日期, m.會員姓名, i.商品名稱, r.數量, r.實收金額 FROM Sales_Record r LEFT JOIN Member m ON r.會員ID = m."會員ID*" LEFT JOIN Product_Item i ON r.商品ID = i."商品ID*" ORDER BY r.銷售日期 DESC'
            msg = "🧑‍💼 [員工權限] 營收銷售紀錄流水帳："

    # ----------------------------------------
    # 分支 2：顧客會員 (嚴格隔離、禁止橫向越權)
    # ----------------------------------------
    elif role == "member":
        if any(keyword in clean_query for keyword in ["員工", "老闆", "薪水", "部門", "全體", "總表", "流水帳"]) or e_id_match:
            return None, "🙅 權限不足：基於隱私權政策，會員帳號禁止存取店內員工檔案或全域營業明細。"
        
        if "商品" in clean_query or "目錄" in clean_query:
            query = 'SELECT 商品名稱, 售價, 品牌 FROM Product_Item'
            msg = "📦 精選寵物商品目錄："
        elif "美容" in clean_query and is_item_query:
            query = "SELECT 美容項目名稱, 適用寵物, 費用, 說明 FROM Grooming_Item"
            msg = "✂️ 美容服務價目表："
        elif "醫療" in clean_query and is_item_query:
            query = "SELECT 醫療項目名稱, 適用寵物, 費用, 說明 FROM Medical_Item"
            msg = "🏥 醫療門診項目收費標準："
        elif "住宿" in clean_query or "旅舍" in clean_query:
            if is_item_query:
                query = "SELECT 旅舍項目名稱, 適用寵物, 每日費用, 說明 FROM Hotel_Item"
                msg = "🏠 寵物旅館型態與每日費用表："
        
        # 🌟 修正：精準的「個人基本資料」查詢，加入 m."會員ID*"，並包含「編號」等詞彙
        elif any(keyword in clean_query for keyword in ["個人資料", "基本資料", "會員資料", "我是誰", "我的檔案", "個人檔案", "編號", "會員編號", "卡號", "等級"]):
            query = f"""
            SELECT m."會員ID*", m.會員姓名, m.電話, m.Email, m.會員等級, p.寵物名稱, p.品種, p.出生日期
            FROM Member m
            LEFT JOIN Pet p ON m."會員ID*" = p.會員ID
            WHERE m.電話 = '{user_phone}'
            """
            msg = "👤 您好！以下是您的專屬會員編號與基本資料："

        # 💡 修正：把「我的」、「查詢」、「資料」這種太容易誤判的字拿掉，改用更具體的消費名詞
        elif any(keyword in clean_query for keyword in ["紀錄", "消費", "歷史", "預約", "看診", "明細", "花費", "過去"]):
            query = f"""
            SELECT p.寵物名稱, p.寵物類型, p.品種, r.美容日期 AS 日期, r.美容項目 AS 項目_原因, r.總金額, r.狀態, '美容紀錄' AS 類別
            FROM Member m JOIN Pet p ON m."會員ID*" = p.會員ID JOIN Grooming_Record r ON p."寵物ID*" = r.寵物ID WHERE m.電話 = '{user_phone}'
            UNION ALL
            SELECT p.寵物名稱, p.寵物類型, p.品種, r.看診日期 AS 日期, r.醫療項目 AS 項目_原因, r.總金額, r.備註 AS 狀態, '醫療紀錄' AS 類別
            FROM Member m JOIN Pet p ON m."會員ID*" = p.會員ID JOIN Medical_Record r ON p."寵物ID*" = r.寵物ID WHERE m.電話 = '{user_phone}'
            UNION ALL
            SELECT p.寵物名稱, p.寵物類型, p.品種, r.入住日期 AS 日期, r.旅舍項目 AS 項目_原因, r.總金額, r.狀態, '住宿紀錄' AS 類別
            FROM Member m JOIN Pet p ON m."會員ID*" = p.會員ID JOIN Hotel_Record r ON p."寵物ID*" = r.寵物ID WHERE m.電話 = '{user_phone}'
            ORDER BY 日期 DESC
            """
            msg = f"👑 您好！已自動為您調閱專屬於您的電話 ({user_phone}) 歷史紀錄："

    # 執行本地端規則 SQL
    if query:
        try:
            df = execute_sql(query)
            if df.empty:
                return None, "查無符合條件的數據資料喔。"
            return df, msg
        except Exception:
            return None, f"系統查詢發生異常，請重試。"

    # ----------------------------------------
    # 引擎 3：Gemini AI 智能大腦 (如果沒有 API Key，直接擋下)
    # ----------------------------------------
    if not API_KEY:
        return None, "💡 系統尚未偵測到 Gemini API Key，目前無法啟動 AI 問答模式。請確認您的 .streamlit/secrets.toml 設定是否正確。"

    try:
        llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.2, google_api_key=API_KEY)
        
        if role == "member":
            ai_prompt = f"你是一位親切的寵物店線上客服專家。使用者問了以下問題，請用繁體中文給予溫暖且專業的飼養常識建議：\n\n問題：{user_query}"
            response = llm.invoke(ai_prompt).content.strip()
            return None, response
            
        elif role == "employee":
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
            【限制】主鍵如 "會員ID*" 需加雙引號：Member."會員ID*"
            """
            routing_prompt = f"""
            判斷問題：
            如果是查詢寵物店內部資料，根據以下結構輸出純 SQL 語法 (不要加 ```sql 標記)。
            如果是一般聊天或建議，直接用人類口吻回答，並在最前方加上「CHAT:」。
            資料庫結構：{schema_info}
            使用者提問：{user_query}
            """
            ai_response = llm.invoke(routing_prompt).content.strip()
            
            if ai_response.startswith("CHAT:"):
                return None, ai_response.replace("CHAT:", "").strip()
            else:
                sql_query = ai_response.replace("```sql", "").replace("```", "").strip()
                df = execute_sql(sql_query)
                if df.empty:
                    return None, "🤖 AI 分析完畢，但查無符合條件的數據資料。"
                return df, "🤖 AI 智能跨表分析結果："
                
    except Exception as e:
        error_msg = str(e).lower()
        if "429" in error_msg or "quota" in error_msg:
            return None, "⏳ AI 大腦目前流量管制中，請稍後再試。"
        return None, f"⚠️ AI 處理發生異常：\n{e}"

# ==========================================
# 5. 聊天介面渲染區
# ==========================================
st.subheader("🐾 歡迎使用智慧諮詢中心")

if st.session_state.role is None:
    st.warning("👋 歡迎光臨！本系統包含個資防護。請先使用左側側邊欄進行【會員手機號碼登入】或【員工認證】，即可開始查詢。")
else:
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            if "dataframe" in msg and msg["dataframe"] is not None:
                st.dataframe(msg["dataframe"], use_container_width=True)
            st.markdown(msg["content"])

    if prompt := st.chat_input("請在此輸入您的問題..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("系統正在處理中..."):
                df_result, text_response = secure_query(prompt, st.session_state.role, st.session_state.user_phone)
                if df_result is not None:
                    st.dataframe(df_result, use_container_width=True)
                st.markdown(text_response)
            
        st.session_state.messages.append({"role": "assistant", "content": text_response, "dataframe": df_result})
