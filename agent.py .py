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


instruct_chat = ChatNVIDIA(model="mistralai/mistral-7b-instruct-v0.2")



class KnowledgeBase(BaseModel):
    first_name: str = Field('unknown', description="Chatting user's first name, `unknown` if unknown")
    last_name: str = Field('unknown', description="Chatting user's last name, `unknown` if unknown")
    confirmation: Optional[int] = Field(None, description="Flight Confirmation Number, `-1` if unknown")
    discussion_summary: str = Field("", description="Summary of discussion so far, including locations, issues, etc.")
    open_problems: str = Field("", description="Topics that have not been resolved yet")
    current_goals: str = Field("", description="Current goal for the agent to address")



def RExtract(pydantic_class, llm, prompt):
    '''
    Runnable Extraction module
    Returns a knowledge dictionary populated by slot-filling extraction
    '''
    parser = PydanticOutputParser(pydantic_object=pydantic_class)
    instruct_merge = RunnableAssign({'format_instructions' : lambda x: parser.get_format_instructions()})
    def preparse(string):
        if '{' not in string: string = '{' + string
        if '}' not in string: string = string + '}'
        string = (string
            .replace("\\_", "_")
            .replace("\n", " ")
            .replace("\]", "]")
            .replace("\[", "[")
        )
        print(string)  # =================================
        return string
    return instruct_merge | prompt | llm | preparse | parser



parser_prompt = ChatPromptTemplate.from_template(
    "Update the knowledge base: {format_instructions}. Only use information from the input."
    "\n\nNEW MESSAGE: {input}"
)






def get_flight_info(d: dict) -> str:
    """
    Example of a retrieval function which takes a dictionary as key. Resembles SQL DB Query
    """
    req_keys = ['first_name', 'last_name', 'confirmation']
    assert all((key in d) for key in req_keys), f"Expected dictionary with keys {req_keys}, got {d}"

    ## Static dataset. get_key and get_val can be used to work with it, and db is your variable
    keys = req_keys + ["departure", "destination", "departure_time", "arrival_time", "flight_day"]
    values = [
        ["Jane", "Doe", 12345, "San Jose", "New Orleans", "12:30 PM", "9:30 PM", "tomorrow"],
        ["John", "Smith", 54321, "New York", "Los Angeles", "8:00 AM", "11:00 AM", "Sunday"],
        ["Alice", "Johnson", 98765, "Chicago", "Miami", "7:00 PM", "11:00 PM", "next week"],
        ["Bob", "Brown", 56789, "Dallas", "Seattle", "1:00 PM", "4:00 PM", "yesterday"],
    ]
    get_key = lambda d: "|".join([d['first_name'], d['last_name'], str(d['confirmation'])])
    get_val = lambda l: {k:v for k,v in zip(keys, l)}
    db = {get_key(get_val(entry)) : get_val(entry) for entry in values}

    # Search for the matching entry
    data = db.get(get_key(d))
    if not data:
        return (
            f"Based on {req_keys} = {get_key(d)}) from your knowledge base, no info on the user flight was found."
            " This process happens every time new info is learned. If it's important, ask them to confirm this info."
        )
    return (
        f"{data['first_name']} {data['last_name']}'s flight from {data['departure']} to {data['destination']}"
        f" departs at {data['departure_time']} {data['flight_day']} and lands at {data['arrival_time']}."
    )



# print(get_flight_info({"first_name" : "Jane", "last_name" : "Doe", "confirmation" : 12345}))



def get_key_fn(base: BaseModel) -> dict:
    '''Given a dictionary with a knowledge base, return a key for get_flight_info'''
    return {  
        'first_name' : base.first_name,
        'last_name' : base.last_name,
        'confirmation' : base.confirmation,
    }

know_base = KnowledgeBase(first_name = "Jane", last_name = "Doe", confirmation = 12345)

# get_flight_info(get_key_fn(know_base))

get_key = RunnableLambda(get_key_fn)



external_prompt = ChatPromptTemplate.from_messages([
    ("system", (
        "You are a chatbot for SkyFlow Airlines, and you are helping a customer with their issue."
        " Please chat with them! Stay concise and clear!"
        " Your running knowledge base is: {know_base}."
        " This is for you only; Do not mention it!"
        " \nUsing that, we retrieved the following: {context}\n"
        " If they provide info and the retrieval fails, ask to confirm their first/last name and confirmation."
        " Do not ask them any other personal info."
        " If it's not important to know about their flight, do not ask."
        " The checking happens automatically; you cannot check manually."
    )),
    
    ("user", "{input}"),
])



parser_prompt = ChatPromptTemplate.from_template(
    "You are a chat assistant representing the airline SkyFlow, and are trying to track info about the conversation."
    " You have just received a message from the user. Please fill in the schema based on the chat."
    "\n\n{format_instructions}"
    "\n\nOLD KNOWLEDGE BASE: {know_base}"
    
    "\n\nUSER MESSAGE: {input}"
    "\n\nNEW KNOWLEDGE BASE: "
)

## Your goal is to invoke the following through natural conversation
# get_flight_info({"first_name" : "Jane", "last_name" : "Doe", "confirmation" : 12345}) ->
#     "Jane Doe's flight from San Jose to New Orleans departs at 12:30 PM tomorrow and lands at 9:30 PM."

chat_llm = ChatNVIDIA(model="mistralai/mistral-7b-instruct-v0.2") | StrOutputParser()
instruct_llm = ChatNVIDIA(model="mistralai/mistral-7b-instruct-v0.2") | StrOutputParser()

external_chain = external_prompt | chat_llm


knowbase_getter = lambda x: RExtract(KnowledgeBase, instruct_llm, parser_prompt)


database_getter = lambda x: itemgetter('know_base') | get_key | get_flight_info


internal_chain = (
    RunnableAssign({'know_base' : knowbase_getter})
    | RunnableAssign({'context' : database_getter})
)



state = {'know_base' : KnowledgeBase()}

def chat_gen(message, history=[], return_buffer=True):

    
    global state
    state['input'] = message
    state['history'] = history
    state['output'] = "" if not history else history[-1][1]

    
    state = internal_chain.invoke(state)
    print("State after chain run:")
    print({k:v for k,v in state.items() if k != "history"})

    
    buffer = ""
    for token in external_chain.stream(state):
        buffer += token
        yield buffer if return_buffer else token

def queue_fake_streaming_gradio(chat_stream, history = [], max_questions=8):

    
    for human_msg, agent_msg in history:
        if human_msg: print("\n[ Human ]:", human_msg)
        if agent_msg: print("\n[ Agent ]:", agent_msg)

    ## Mimic of the gradio loop with an initial message from the agent.
    for _ in range(max_questions):
        message = input("\n[ Human ]: ")
        print("\n[ Agent ]: ")
        history_entry = [message, ""]
        for token in chat_stream(message, history, return_buffer=False):
            print(token, end='')
            history_entry[1] += token
        history += [history_entry]
        print("\n")


chat_history = [[None, "Hello! I'm your SkyFlow agent! How can I help you?"]]


queue_fake_streaming_gradio(
    chat_stream = chat_gen,
    history = chat_history
)


