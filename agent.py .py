import os
import sqlite3
from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import tool
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_nvidia_ai_endpoints import ChatNVIDIA, NVIDIAEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_community.document_loaders import TextLoader
from langchain.text_splitter import CharacterTextSplitter
from langchain.tools.retriever import create_retriever_tool

load_dotenv()

os.getenv("NVIDIA_API_KEY")
    
DB_FILE = "parlant.db"

def setup_database():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS customers (
        user_id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        scheme TEXT,
        last_credit TEXT,
        auth_secret TEXT 
    )
    """)
    sample_data = [
        ('ramesh', 'Ramesh', 'PM-Kisan', '₹2000 on 23-Aug', '1234'),
        ('aadhaar123', 'Sita', 'NREGA', '₹2500 on 15-Aug', 'abcd')
    ]
    cursor.executemany("INSERT OR IGNORE INTO customers VALUES (?, ?, ?, ?, ?)", sample_data)
    conn.commit()
    conn.close()
    print("Database setup complete.")

@tool
def authenticate_customer(identifier: str, secret: str) -> str:
    """
    Authenticates a customer using their identifier (like 'ramesh' or 'aadhaar123') and a secret password.
    Call this tool when a user wants to log in or check their account.
    """
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM customers WHERE user_id = ? AND auth_secret = ?",
        (identifier, secret)
    )
    result = cursor.fetchone()
    conn.close()
    if result:
        return f"Authentication successful for user {identifier}."
    else:
        return "Authentication failed. Please check your details."

@tool
def get_account_info(user_id: str) -> str:
    """
    After a customer is authenticated, use this tool to fetch their account information
    like their scheme, name, and last credited amount using their user_id.
    """
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT name, scheme, last_credit FROM customers WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    conn.close()
    if result:
        info = dict(result)
        return f"Account Information for {info['name']}: Scheme is {info['scheme']}. Last credit was {info['last_credit']}."
    else:
        return "Account not found for that user ID. The user must be authenticated first."

def create_scheme_retriever_tool():
    """
    Creates a retriever tool that can search the 'schemes.txt' file for information.
    The agent uses this to answer questions about scheme details, eligibility, etc.
    """
    loader = TextLoader("./schemes.txt")
    documents = loader.load()
    text_splitter = CharacterTextSplitter(chunk_size=500, chunk_overlap=0)
    docs = text_splitter.split_documents(documents)
    embeddings = NVIDIAEmbeddings()
    vectorstore = FAISS.from_documents(docs, embeddings)
    retriever = vectorstore.as_retriever()
    
    return create_retriever_tool(
        retriever,
        "scheme_information_retriever",
        "Search for information about government schemes like NREGA, PM-Kisan, eligibility, and application processes.",
    )

def main():
    setup_database()
    
    tools = [
        authenticate_customer,
        get_account_info,
        create_scheme_retriever_tool()
    ]

    system_prompt = """You are "PRAGATI", a smart, AI-powered assistant for rural communities in India.
Your full name is Propagation for Rural AI Gateway And Transaction Inquiry.

Your primary goal is to help users check their government benefit status (like NREGA wages or PM-Kisan subsidies).

**Language Rule: Your MOST IMPORTANT rule is to detect the user's language (English, Hindi, Telugu, or Malayalam) in their first message and respond ONLY in that language for the entire conversation.**

**Your Capabilities & Rules:**
1.  **Greeting:** When a user greets you, respond warmly in their language and introduce yourself as PRAGATI.
2.  **Authentication:** If a user wants to check their account, ask for their identifier and secret. Then use the `authenticate_customer` tool. Do not ask for information you don't need.
3.  **Account Info:** Once authenticated, if they ask for their account details, use the `get_account_info` tool with their user_id.
4.  **Scheme Questions:** If a user asks about *how a scheme works*, its *eligibility*, or the *application process*, use the `scheme_information_retriever` tool to find the answer.
5.  **Synonyms:** You understand that NREGA is the same as MGNREGA, मनरेगा, or തൊഴിലുറപ്പ് പദ്ധതി.
6.  **Frustration:** If a user is frustrated about payment delays, be empathetic. Explain that local authorities handle payments and suggest they check with their local Gram Panchayat.
7.  **Scope:** If asked an unrelated question, politely state that you can only help with government schemes and redirect them.
"""

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("placeholder", "{chat_history}"),
        ("human", "{input}"),
        ("placeholder", "{agent_scratchpad}"),
    ])

    llm = ChatNVIDIA(model="meta/llama3-70b-instruct")

    agent = create_tool_calling_agent(llm, tools, prompt)

    agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)

    print("\nPRAGATI Agent is running. Type your questions below!")
    print("   (Try asking in Hindi, Telugu, or Malayalam too!)")
    
    chat_history = []
    
    while True:
        user_input = input("\nYou: ")
        if user_input.lower() in {"exit", "quit", "bye"}:
            print("Agent: Namaste! Thank you for using PRAGATI. Goodbye! 👋")
            break
        
        result = agent_executor.invoke({
            "input": user_input,
            "chat_history": chat_history
        })
        
        print(f"Agent: {result['output']}")
        
        chat_history.append({"role": "user", "content": user_input})
        chat_history.append({"role": "assistant", "content": result['output']})

if __name__ == "__main__":
    main()
