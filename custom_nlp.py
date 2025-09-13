from langchain_nvidia_ai_endpoints import ChatNVIDIA
from langchain.output_parsers import PydanticOutputParser
from langchain_core.runnables import RunnableLambda
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from operator import itemgetter
from langchain.schema.runnable.passthrough import RunnableAssign
from pydantic import BaseModel, Field
from typing import Dict, Union, Optional
from dotenv import load_dotenv
import os

load_dotenv()
os.environ.get("NVIDIA_API_KEY")

instruct_chat = ChatNVIDIA(model="mistralai/mixtral-8x22b-instruct-v0.1")
instruct_llm = ChatNVIDIA(model="mistralai/mixtral-8x22b-instruct-v0.1") | StrOutputParser()
chat_llm = ChatNVIDIA(model="mistralai/mixtral-8x22b-instruct-v0.1") | StrOutputParser()


language = "malayalam"

class KnowledgeBase(BaseModel):
    user_id: str = Field('unknown', description="User Aadhaar or identifier, `unknown` if unknown")
    authentication_status: Optional[bool] = Field(None, description="Whether user is authenticated")
    discussion_summary: str = Field("", description="Summary of discussion so far")
    open_problems: str = Field("", description="Open issues yet to be resolved")
    current_goals: str = Field("", description="What is the current goal of the interaction")


def get_scheme_info(user_data: dict) -> str:
    """
    Simulates DB lookup for user scheme info based on user_id
    """
    db = {
        "aadhaar123": {"name": "Sita", "scheme": "NREGA", "last_credit": "₹2500 on 15-Aug"},
        "aadhaar456": {"name": "Ramesh", "scheme": "PM-Kisan", "last_credit": "₹2000 on 23-Aug"},
    }

    user_id = user_data['user_id']
    data = db.get(user_id)

    if not data:
        return {
            "english": "No record found for the provided identifier.",
            "hindi": "प्रदान किए गए पहचानकर्ता के लिए कोई रिकॉर्ड नहीं मिला।",
            "malayalam": "നൽകിയ തിരിച്ചറിയൽക്കായി റെക്കോർഡ് കണ്ടെത്തിയില്ല.",
            "telugu": "నివ్వబడిన గుర్తింపు కోసం రికార్డు కనుగొనబడలేదు."
        }[language]

    responses = {
        "english": f"{data['name']} is registered under the {data['scheme']} scheme. Last credit was {data['last_credit']}.",
        "hindi": f"{data['name']} {data['scheme']} योजना के अंतर्गत पंजीकृत हैं। अंतिम भुगतान {data['last_credit']} था।",
        "malayalam": f"{data['name']} {data['scheme']} സ്കീമിൽ രജിസ്റ്റർ ചെയ്തിരിക്കുന്നു. അവസാന ക്രെഡിറ്റ് {data['last_credit']}.",
        "telugu": f"{data['name']} {data['scheme']} పథకంలో నమోదు అయ్యారు. చివరి చెల్లింపు {data['last_credit']}."
    }

    return responses[language]



def get_key_fn(base: BaseModel) -> dict:
    return {'user_id': base.user_id}


parser_prompt = ChatPromptTemplate.from_template(
    "Update the knowledge base: {format_instructions}. Only use information from the input."
    "\n\nNEW MESSAGE: {input}"
)




external_prompt = ChatPromptTemplate.from_messages([
    ("system", (
        "You are PRAGATI, a smart agent helping rural citizens to check NREGA or other government schemes."
        " You must answer in the global language: " + language + "."
        " This is private knowledge: {know_base}."
        " We retrieved the following user info: {context}."
        " Respond concisely and helpfully."
    )),
    
    ("user", "{input}"),
])

get_key = RunnableLambda(get_key_fn)

def RExtract(pydantic_class, llm, prompt):
    parser = PydanticOutputParser(pydantic_object=pydantic_class)
    instruct_merge = RunnableAssign({'format_instructions' : lambda x: parser.get_format_instructions()})
    def preparse(string):
        if '{' not in string: string = '{' + string
        if '}' not in string: string = string + '}'
        string = (string.replace("\\_", "_").replace("\n", " ").replace("\]", "]").replace("\[", "["))
        return string
    return instruct_merge | prompt | llm | preparse | parser

knowbase_getter = lambda x: RExtract(KnowledgeBase, instruct_llm, parser_prompt)

database_getter = lambda x: itemgetter('know_base') | get_key | get_scheme_info

internal_chain = (
    RunnableAssign({'know_base': knowbase_getter})
    | RunnableAssign({'context': database_getter})
)





external_chain = external_prompt | chat_llm



state = {'know_base': KnowledgeBase()}

def chat_gen(message, history=[], return_buffer=True):
    global state
    state['input'] = message
    state['history'] = history
    state['output'] = "" if not history else history[-1][1]

    state = internal_chain.invoke(state)

    buffer = ""
    for token in external_chain.stream(state):
        buffer += token
        yield buffer if return_buffer else token

def queue_fake_streaming_gradio(chat_stream, history = [], max_questions=8):
    for human_msg, agent_msg in history:
        if human_msg: print("\n[ Human ]:", human_msg)
        if agent_msg: print("\n[ Agent ]:", agent_msg)

    for _ in range(max_questions):
        message = input("\n[ Human ]: ")
        print("\n[ Agent ]: ")
        history_entry = [message, ""]
        for token in chat_stream(message, history, return_buffer=False):
            print(token, end='')
            history_entry[1] += token
        history += [history_entry]
        print("\n")

chat_history = [[None, "Hello! I'm your PRAGATI agent! How can I help you?"]]

queue_fake_streaming_gradio(
    chat_stream=chat_gen,
    history=chat_history
)

