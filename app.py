import streamlit as st
import tempfile
import os
from langchain_openai import ChatOpenAI
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_classic.chains import create_retrieval_chain
from langchain_classic.chains.combine_documents import create_stuff_documents_chain
from langchain_core.prompts import ChatPromptTemplate

# ==========================================
# 🎨 1. 前端配置 (HTML/CSS)
# ==========================================
st.set_page_config(page_title="Mini-Brain Pro", layout="wide")

# 注入自定义 CSS (装修大堂)
# 我们把聊天气泡的字体改大一点，背景色微调
st.markdown("""
<style>
    .stChatMessage {
        font-family: 'Helvetica Neue', sans-serif;
    }
</style>
""", unsafe_allow_html=True)

st.title("🧠 Mini-Brain Pro: 有记忆的第二大脑")

# ==========================================
# 🧠 2. 后端逻辑：状态管理 (Session State)
# ==========================================

# 初始化聊天记录 (海马体)
# 如果内存里没有 "messages"，就新建一个空列表
if "messages" not in st.session_state:
    st.session_state.messages = []

# 初始化 RAG 链 (大脑)
# 我们把大脑也存在 session_state 里，防止每次点按钮都重载模型（太慢）
if "qa_chain" not in st.session_state:
    st.session_state.qa_chain = None

# ==========================================
# ⚙️ 3. 侧边栏：配置与数据处理
# ==========================================
with st.sidebar:
    st.header("🔧 配置控制台")
    api_key = st.text_input("API Key", type="password")
    base_url = st.text_input("Base URL", value="https://api.deepseek.com")
    
    st.divider()
    
    uploaded_file = st.file_uploader("📂 上传 PDF 喂给大脑", type="pdf")
    
    # 当用户上传文件后，触发数据处理流水线
    if uploaded_file and api_key and not st.session_state.qa_chain:
        with st.spinner("正在切片、向量化、存入数据库..."):
            # A. 保存临时文件
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                tmp.write(uploaded_file.getvalue())
                tmp_path = tmp.name
            
            # B. 加载与切分
            loader = PyPDFLoader(tmp_path)
            docs = loader.load()
            splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
            splits = splitter.split_documents(docs)
            
            # C. 向量化 (Embeddings)
            embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
            
            # D. 存入 Chroma (Vector Store)
            vectorstore = Chroma.from_documents(splits, embeddings)
            
            # E. 组装大脑
            llm = ChatOpenAI(
                model="deepseek-chat", 
                api_key=api_key, 
                base_url=base_url,
                temperature=0
            )
            
            # F. 保存到后端状态里
            prompt = ChatPromptTemplate.from_messages([
                ("system", "Use the given context to answer the question. If you don't know the answer, say you don't know. Use three sentence maximum and keep the answer concise. Context: {context}"),
                ("human", "{input}"),
            ])
            question_answer_chain = create_stuff_documents_chain(llm, prompt)
            st.session_state.qa_chain = create_retrieval_chain(
                vectorstore.as_retriever(), question_answer_chain
            )
            
            st.success("✅ 大脑已激活！可以开始对话了。")
            os.remove(tmp_path) # 清理临时文件

# ==========================================
# 💬 4. 主界面：聊天循环 (Event Loop)
# ==========================================

# A. 渲染历史消息 (把后端内存里的东西画到前端页面上)
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# B. 监听用户输入
if prompt := st.chat_input("向你的文档提问..."):
    
    # 1. 检查有没有激活大脑
    if not st.session_state.qa_chain:
        st.error("请先在左侧配置 API 并上传文件！")
        st.stop()

    # 2. 显示用户消息 (前端)
    with st.chat_message("user"):
        st.markdown(prompt)
    
    # 3. 记入历史 (后端)
    st.session_state.messages.append({"role": "user", "content": prompt})

    # 4. 调用 AI 思考
    with st.chat_message("assistant"):
        with st.spinner("思考中..."):
            # 调用 RAG 链
            response = st.session_state.qa_chain.invoke({"input": prompt})
            result = response["answer"]
            st.markdown(result)
            
    # 5. 记入历史 (后端)
    st.session_state.messages.append({"role": "assistant", "content": result})