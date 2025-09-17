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
import re

load_dotenv()
os.environ.get("NVIDIA_API_KEY")

def extract_aadhaar(text):

    match = re.search(r'\b(\d{3,12})\b', text)
    if match:
        return match.group(1)
    return 'unknown'

instruct_chat = ChatNVIDIA(model="mistralai/mixtral-8x22b-instruct-v0.1")
instruct_llm = ChatNVIDIA(model="mistralai/mixtral-8x22b-instruct-v0.1") | StrOutputParser()
chat_llm = ChatNVIDIA(model="mistralai/mixtral-8x22b-instruct-v0.1") | StrOutputParser()


# language = "malayalam"

class KnowledgeBase(BaseModel):
    user_id: str = Field('unknown', description="User Aadhaar Number of user, `unknown` if unknown")
    # full_name: str = Field('unknown', description="Full name of the user, `unknown` if unknown")
    authentication_status: Optional[bool] = Field(None, description="Whether user is authenticated")
    discussion_summary: str = Field("", description="Summary of discussion so far")
    open_problems: str = Field("", description="Open issues yet to be resolved")
    current_goals: str = Field("", description="What is the current goal of the interaction")


def get_scheme_info(user_data: dict, language_for_agent) -> str:
    """
    Simulates DB lookup for user scheme info, matching both user_id (Aadhaar) and full name.
    """
    db = {
        "426456": {"name": "Sita", "scheme": "NREGA", "last_credit": "₹2500 on 15-Aug"},
        "13456": {"name": "Ramesh", "scheme": "PM-Kisan", "last_credit": "₹2000 on 23-Aug"},
    }

    user_id = user_data['user_id']
    # full_name = user_data.get('full_name', "").strip().lower()

    data = db.get(user_id)

    if not data: #if not data or data['name'].lower() != full_name:
        return {
            "english": "No record found matching the provided Aadhaar.",
            "hindi": "प्रदान किए गए आधार और पूरा नाम के लिए कोई रिकॉर्ड नहीं मिला।",
            "malayalam": "നൽകിയ ആദായവും മുഴുവൻ പേരും പൊരുത്തപ്പെടുന്ന രേഖയൊന്നും കണ്ടെത്തിയില്ല.",
            "telugu": "నివ్వబడిన ఆధార్ మరియు పూర్తి పేరుతో సరిపోయే రికార్డు కనుగొనబడలేదు."
        }[language_for_agent]

    responses = {
        "english": f"{data['name']} is registered under the {data['scheme']} scheme. Last credit was {data['last_credit']}.",
        "hindi": f"{data['name']} {data['scheme']} योजना के अंतर्गत पंजीकृत हैं। अंतिम भुगतान {data['last_credit']} था।",
        "malayalam": f"{data['name']} {data['scheme']} സ്കീമിൽ രജിസ്റ്റർ ചെയ്തിരിക്കുന്നു. അവസാന ക്രെഡിറ്റ് {data['last_credit']}.",
        "telugu": f"{data['name']} {data['scheme']} పథకంలో నమోదు అయ్యారు. చివరి చెల్లింపు {data['last_credit']}."
    }

    return responses[language_for_agent]




def get_key_fn(base: BaseModel) -> dict:
    return {
        'user_id': base.user_id,
        # 'full_name': base.full_name
    }



parser_prompt = ChatPromptTemplate.from_template(
    "Update the knowledge base: {format_instructions}. Only use information from the input."
    "\n\nNEW MESSAGE: {input}"
)



def external_prompt(language_for_agent):
    return ChatPromptTemplate.from_messages([
        ("system", (
            "You are PRAGATI, a smart agent helping rural citizens to check their government scheme status like NREGA or PM-Kisan."
            " Always respond in the global language selected: " + language_for_agent + ", provie short response in one language."
            " Do not mix languages. If the user tries to mix languages, respond in " + language_for_agent + " only, and don't mention it to the user to use one language."
            " Ensure the user provides Aadhaar number so you can verify their identity."
            " This is private knowledge: {know_base}."
            " We retrieved the following user info: {context}."
            " Provide a clear, concise, and helpful answer regarding the user's scheme status or last transaction."
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

def database_getter(user_data):
    language_for_agent = user_data.get('language_for_agent')
    key_data = {'user_id': user_data.get('user_id', 'unknown')}
    return get_scheme_info(key_data, language_for_agent)



internal_chain = (
    RunnableAssign({'know_base': knowbase_getter})
    | RunnableAssign({'context': database_getter})
)





external_chain = external_prompt | chat_llm



state = {'know_base': KnowledgeBase()}

def chat_gen(message, language_for_agent, history=[], return_buffer=True):
    global state
    state['input'] = message
    state['history'] = history
    state['output'] = "" if not history else history[-1][1]
    state['language_for_agent'] = language_for_agent
    state['user_id'] = extract_aadhaar(message)  

    state = internal_chain.invoke(state)

    external_chain = external_prompt(language_for_agent) | chat_llm

    buffer = ""
    for token in external_chain.stream(state):
        buffer += token
        yield buffer if return_buffer else token

def queue_streaming(chat_stream, history = [], max_questions=8):
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

greetings = {
    "english": "Hello! I am your PRAGATI agent here to help you check your government scheme status.",
    "hindi": "नमस्ते! मैं आपका प्रगति एजेंट हूँ, आपकी सरकारी योजना स्थिति जांचने में मदद करने के लिए।",
    "malayalam": "നമസ്കാരം! ഞാൻ നിങ്ങളുടെ പ്രഗതി പ്രതിനിധിയാണ്, സർക്കാർ പദ്ധതികളുടെ സ്ഥിതി പരിശോധിക്കാൻ നിങ്ങളെ സഹായിക്കാൻ ഇവിടെ വന്നിരിക്കുന്നു.",
    "telugu": "నమస్కారం! నేను మీ ప్రగతి ఏజెంట్, మీరు మీ ప్రభుత్వ పథక స్థితిని తనిఖీ చేయడంలో సహాయపడటానికి ఉన్నాను."
}

def initial_greeting(lang: str) -> str:
    return greetings.get(lang, greetings['english'])  


# chat_history = [[None, initial_greeting(language_for_agent)]]

# queue_streaming(
#     chat_stream=chat_gen,
#     history=chat_history
# )


