import os
import asyncio
from dotenv import load_dotenv

import parlant.sdk as p
from parlant.core.nlp.generation import SchematicGenerator
from azure.ai.inference import ChatCompletionsClient
from azure.ai.inference.models import SystemMessage, UserMessage
from azure.core.credentials import AzureKeyCredential
from parlant.core.nlp.generation import SchematicGenerator
from parlant.core.nlp.service import NLPService
from parlant.core.nlp.embedding import Embedder, EmbeddingResult
from parlant.core.nlp.moderation import ModerationService, ModerationCheck, ModerationTag

from openai import AsyncOpenAI

# ===============================
# 1. Load API key from .env
# ===============================
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")


if not GITHUB_TOKEN:
    raise ValueError("GITHUB_TOKEN not found in .env file")

class GitHubModelsGenerator(SchematicGenerator):
    def __init__(self):
        self.endpoint = "https://models.github.ai/inference"
        self._id = "openai/gpt-4o-mini"
        self.client = ChatCompletionsClient(
            endpoint=self.endpoint,
            credential=AzureKeyCredential(GITHUB_TOKEN),
        )
        self._max_tokens = 2048

    @property
    def id(self) -> str:
        return self._id

    @property
    def max_tokens(self) -> int:
        return self._max_tokens

    @property
    def tokenizer(self):
        class DummyTokenizer:
            async def estimate_token_count(self, prompt: str) -> int:
                return len(prompt.split())
        return DummyTokenizer()

    async def generate(self, prompt: str, hints: dict = {}) -> p.SchematicGenerationResult:
        messages = [
            SystemMessage("You are a helpful and concise AI assistant."),
            UserMessage(prompt)
        ]
        try:
            response = await asyncio.to_thread(
                self.client.complete,
                messages=messages,
                model=self._id,
                max_tokens=self._max_tokens,
                temperature=hints.get("temperature", 0.3),
            )
            text = response.choices[0].message.content or "No response from model"
            input_tokens = response.usage.prompt_tokens if hasattr(response, 'usage') else len(prompt.split())
            output_tokens = response.usage.completion_tokens if hasattr(response, 'usage') else len(text.split())
        except Exception as e:
            text = f"An error occurred with the API: {str(e)}"
            input_tokens = len(prompt.split())
            output_tokens = 0

        return p.SchematicGenerationResult(
            content=text,
            info=p.GenerationInfo(
                schema_name="string",
                model=self._id,
                duration=0.0,
                usage=p.UsageInfo(input_tokens=input_tokens, output_tokens=output_tokens),
            ),
        )

class CustomModerationService(ModerationService):
    async def check(self, content: str) -> ModerationCheck:
        return ModerationCheck(flagged=False, tags=[])

class CustomEmbedder(Embedder):
    @property
    def id(self) -> str: return "custom/embedder"
    @property
    def dimensions(self) -> int: return 100
    @property
    def max_tokens(self) -> int: return 1000
    @property
    def tokenizer(self):
        class DummyTokenizer:
            async def estimate_token_count(self, prompt: str) -> int: return len(prompt.split())
        return DummyTokenizer()
    async def embed(self, texts: list[str], hints: dict = {}) -> EmbeddingResult:
        vectors = [[0.0] * 100 for _ in texts]
        return EmbeddingResult(vectors=vectors)

class GitHubModelsNLPService(NLPService):
    @staticmethod
    def verify_environment() -> str | None:
        if not os.environ.get("GITHUB_TOKEN"):
            return "GITHUB_TOKEN is not set."
        return None

    async def get_schematic_generator(self, schema):
        return GitHubModelsGenerator()

    async def get_embedder(self) -> Embedder:
        return CustomEmbedder()

    async def get_moderation_service(self) -> ModerationService:
        return CustomModerationService()

# ===============================
# Part 2: Agent Tools and Setup (from agent.py)
# ===============================
async def authenticate_customer(method: str, identifier: str, secret: str = None) -> bool:
    valid = {
        ("password", "ramesh", "1234"),
        ("biometric", "aadhaar123", "1234"),
        ("otp", "aadhaar123", "1234"),
    }
    return (method, identifier, secret) in valid

async def get_account_info(user_id: str) -> dict:
    db = {
        "ramesh": {"name": "Ramesh", "scheme": "PM-Kisan", "last_credit": "₹2000 on 23-Aug"},
        "aadhaar123": {"name": "Sita", "scheme": "NREGA", "last_credit": "₹2500 on 15-Aug"},
    }
    return db.get(user_id, {"error": "Account not found"})

async def schemes_retriever(context: p.RetrieverContext) -> p.RetrieverResult:
    try:
        query = context.interaction.last_customer_message.content.lower()
        with open("./data/schemes.txt", "r", encoding="utf-8") as f:
            docs = f.readlines()
        matches = [doc.strip() for doc in docs if query in doc.lower()]
        if matches:
            return p.RetrieverResult(matches)
        return p.RetrieverResult([])
    except Exception as e:
        return p.RetrieverResult([f"Retriever error: {str(e)}"])

async def initialize_agent(selected_language_name):
    nlp_service = GitHubModelsNLPService()
    server = p.Server(nlp_service=nlp_service)
    await server.__aenter__()

    agent = await server.create_agent(
        name="PRAGATI - Propagation for Rural AI Gateway And Transaction Inquiry",
        description=f"""PRAGATI is a smart, AI-powered solution that helps rural
        communities check government benefits. The user is currently speaking {selected_language_name}."""
    )

    await agent.create_term(
        name="NREGA",
        description="Mahatma Gandhi National Rural Employment Guarantee Act (MGNREGA)",
        synonyms=[
            "MGNREGA", "NREGA scheme", "100 days job scheme", "employment guarantee scheme",
            "मनरेगा", "मनरेगा योजना", "राष्ट्रीय ग्रामीण रोजगार गारंटी योजना", "महात्मा गांधी राष्ट्रीय ग्रामीण रोजगार गारंटी अधिनियम",
            "మహాత్మా గాంధీ జాతీయ గ్రామీణ ఉపాధి హామీ పథకం", "ఎన్ ఆర్ ఈ జి ఏ",
            "എൻആർഇജിഎ", "തൊഴിലുറപ്പ് പദ്ധതി", "മഹാത്മാഗാന്ധി ദേശീയ ഗ്രാമീണ തൊഴിലുറപ്പ് പദ്ധതി"
        ],
    )

    await agent.attach_retriever(schemes_retriever, id="schemes")
    await agent.register_tool(name="authenticate_customer", func=authenticate_customer)
    await agent.register_tool(name="get_account_info", func=get_account_info)
    
    await agent.create_guideline(
        condition="For every user interaction",
        action=f"IMPORTANT: The user has selected {selected_language_name} as their language. You must generate your entire response ONLY in {selected_language_name}."
    )
    await agent.create_guideline(
        condition="Customer greets (hello, hi, namaste, good morning, etc.)",
        action="Respond with a warm greeting in their language. Thank them for connecting with PRAGATI and offer help with NREGA, PM-Kisan, or other schemes."
    )
    await agent.create_guideline(
        condition="Customer wants to log in or authenticate",
        action="Ask the customer which method they prefer: password, OTP, or biometric. Then call authenticate_customer tool to verify them.",
        tools=[authenticate_customer]
    )
    await agent.create_guideline(
        condition="Authenticated customer asks about NREGA balance, job card, or wage status",
        action="Call get_account_info tool and provide a clear response with scheme name, last credited amount, and pending wages if available.",
        tools=[get_account_info]
    )
    
    return agent, server