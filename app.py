import streamlit as st
import sqlite3
import pandas as pd
import glob
import warnings
from duckduckgo_search import DDGS

warnings.filterwarnings("ignore")

st.set_page_config(page_title="寵物店 AI 諮詢平台", page_icon="🐶")
st.title("🐶 寵物店 AI 諮詢平台")

def f(q):
    a = glob.glob('*.db') + glob.glob('*.sqlite')
    if not a:
        return "找不到資料庫檔案，請確認 .db 檔是否放在同一個資料夾！"
    
    b = a[0]
    c = sqlite3.connect(b)
    
    greetings = ["嗨", "hi", "hello", "哈囉", "你好", "您好", "在嗎"]
    if any(g in q.lower() for g in greetings):
        c.close()
        return "哈囉！我是你的寵物店 AI 助手，今天想查詢會員資料、美容統計，還是有其他寵物問題想上網查查呢？"
        
    e = ["客", "會員", "狗", "貓", "美容", "統計"]
    
    if any(i in q for i in e) and "飼料" not in q and "推薦" not in q:
        if "狗" in q and "客" in q:
            x = """
            SELECT T1.Member_Name, T2.Pet_Name, T2.Pet_Type 
            FROM Member AS T1 
            JOIN Pet AS T2 ON T1.Member_ID = T2.Member_ID 
            WHERE T2.Pet_Type = ?;
            """
            y = pd.read_sql_query(x, c, params=('狗',))
            c.close()
            return y
        elif "統計" in q and "美容" in q:
            x = """
            SELECT STRFTIME('%m', Grooming_Date) AS Month, COUNT(*) AS Total_Records 
            FROM Grooming_Record 
            WHERE STRFTIME('%Y', Grooming_Date) = '2024' 
            GROUP BY Month;
            """
            y = pd.read_sql_query(x, c)
            c.close()
            return y
        else:
            c.close()
            return "尚未設定對應 SQL"
    else:
        c.close()
        d = DDGS().text(q, max_results=3)
        r = ""
        for i in d:
            r += f"**{i['title']}**\n\n{i['body']}\n\n---\n"
        return r

if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": "Hi！我是你的寵物店 AI 助手，請問今天想查什麼資料呢？"}]

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        if isinstance(msg["content"], pd.DataFrame):
            st.dataframe(msg["content"])
        else:
            st.markdown(msg["content"])

if prompt := st.chat_input("請輸入問題..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("查詢中..."):
            response = f(prompt)
            if isinstance(response, pd.DataFrame):
                st.dataframe(response)
            else:
                st.markdown(response)
    st.session_state.messages.append({"role": "assistant", "content": response})
