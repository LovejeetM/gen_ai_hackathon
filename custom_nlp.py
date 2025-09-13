import os
from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_nvidia_ai_endpoints import ChatNVIDIA

load_dotenv()

if not os.getenv("NVIDIA_API_KEY"):
    raise ValueError("NVIDIA_API_KEY not found in .env file! Please get one from https://build.nvidia.com/")

system_prompt = """You are NREGA Assistant, a helpful AI assistant for PRAGATI. \
Your goal is to help users understand NREGA eligibility, benefits, and application steps. \
When a customer greets you (e.g., hello, hi, namaste, good morning), you must respond with a warm greeting in their language, \
thank them for connecting with PRAGATI, and offer help with NREGA, PM-Kisan, or other schemes."""

prompt_template = ChatPromptTemplate.from_messages([
    ("system", system_prompt),
    ("user", "{user_input}")
])

llm = ChatNVIDIA(model="meta/llama3-70b-instruct", temperature=0.3, max_tokens=512)

chain = prompt_template | llm | StrOutputParser()

def main():
    print("NREGA Assistant is ready.")
    print(f"Using model: {llm.model}")

    print("\nTesting agent interaction with a greeting...")
    user_message = "Namaste"
    print(f"\nUser: {user_message}")

    response = chain.invoke({"user_input": user_message})
    print(f"Assistant: {response}")

    print("\nTesting agent interaction with a question...")
    user_message = "What are the benefits of NREGA?"
    print(f"\nUser: {user_message}")
    
    response = chain.invoke({"user_input": user_message})
    print(f"Assistant: {response}")

if __name__ == "__main__":
    main()