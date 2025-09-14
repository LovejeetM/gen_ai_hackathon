import os
from dotenv import load_dotenv
from langchain_nvidia_ai_endpoints import ChatNVIDIA, NVIDIAEmbeddings
from langchain_nvidia_ai_endpoints import ChatNVIDIA
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from operator import itemgetter
import numpy as np
import matplotlib.pyplot as plt
from sklearn.metrics.pairwise import cosine_similarity

load_dotenv()
os.environ.get("NVIDIA_API_KEY")


embedder = NVIDIAEmbeddings(model="nvidia/nv-embed-v1")

instruct_llm = ChatNVIDIA(model="mistralai/mixtral-8x7b-instruct-v0.1")


def read_schemes_file():
    schemes = []
    with open("schemes.txt", "r", encoding="utf-8") as file:
        content = file.read().strip()
        
        scheme_blocks = content.split('\n\n')
        for block in scheme_blocks:
            
            cleaned_block = block.strip()
            if cleaned_block:
                schemes.append(cleaned_block)
    return schemes


schemes = read_schemes_file()


queries = [f"Tell me about the {scheme.split(':')[0]}" for scheme in schemes]


q_embeddings = [embedder.embed_query(query) for query in queries]


d_embeddings = embedder.embed_documents(schemes)


import json
import os


if not os.path.exists("embeddings"):
    os.makedirs("embeddings")


data = {
    "schemes": schemes,
    "query_embeddings": q_embeddings,
    "scheme_embeddings": d_embeddings
}

with open("embeddings/schemes_embeddings.json", "w", encoding="utf-8") as file:
    json.dump(data, file, indent=2)

print(f"Processed {len(schemes)} schemes and created embeddings.")
print("Embeddings saved to embeddings/schemes_embeddings.json")

