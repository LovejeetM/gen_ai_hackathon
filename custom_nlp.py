import os
import asyncio
from dotenv import load_dotenv

import parlant.sdk as p
from parlant.core.nlp.generation import SchematicGenerator

from openai import AsyncOpenAI

# ===============================
# 1. Load API key from .env
# ===============================
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY not found")

# ===============================
# 2. OpenAI client wrapper
# ===============================
class OpenAISchematicGenerator(SchematicGenerator):
    def __init__(self):
        self.client = AsyncOpenAI(api_key=OPENAI_API_KEY)
        self._id = "gpt-4o-mini"
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
        try:
            response = await self.client.chat.completions.create(
                model=self._id,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=self._max_tokens,
                temperature=hints.get("temperature", 0.3),
            )
            text = response.choices[0].message.content or "No response from OpenAI"
            input_tokens = response.usage.prompt_tokens
            output_tokens = response.usage.completion_tokens
        except Exception as e:
            text = f"An error occurred with the OpenAI API: {str(e)}"
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

# ===============================
# 3. Custom NLP service implementation
# ===============================
from parlant.core.nlp.service import NLPService
from parlant.core.nlp.embedding import Embedder, EmbeddingResult
from parlant.core.nlp.moderation import ModerationService, ModerationCheck, ModerationTag
from parlant.core.loggers import Logger

class CustomModerationService(ModerationService):
    def __init__(self):
        pass

    async def check(self, content: str) -> ModerationCheck:
        inappropriate_words = ['spam', 'scam', 'fraud']
        flagged = any(word in content.lower() for word in inappropriate_words)

        return ModerationCheck(
            flagged=flagged,
            tags=[ModerationTag.ILLICIT] if flagged else []
        )

class CustomEmbedder(Embedder):
    def __init__(self):
        self._dimensions = 100

    @property
    def id(self) -> str:
        return "custom/embedder"

    @property
    def dimensions(self) -> int:
        return self._dimensions

    @property
    def max_tokens(self) -> int:
        return 1000

    @property
    def tokenizer(self):
        class DummyTokenizer:
            async def estimate_token_count(self, prompt: str) -> int:
                return len(prompt.split())
        return DummyTokenizer()

    async def embed(self, texts: list[str], hints: dict = {}) -> EmbeddingResult:
        vectors = []
        for text in texts:
            words = text.lower().split()
            embedding = [words.count(word) for word in set(words)]
            vectors.append((embedding + [0] * self._dimensions)[:self._dimensions])

        return EmbeddingResult(vectors=vectors)

class OpenAINLPService(NLPService):
    @staticmethod
    def verify_environment() -> str | None:
        if not os.environ.get("OPENAI_API_KEY"):
            return """\
You're using the OpenAI NLP service, but OPENAI_API_KEY is not set.
Please set OPENAI_API_KEY in your environment before running Parlant.
"""
        return None

    def __init__(self):
        pass

    async def get_schematic_generator(self, schema):
        return OpenAISchematicGenerator()

    async def get_embedder(self) -> Embedder:
        return CustomEmbedder()

    async def get_moderation_service(self) -> ModerationService:
        return CustomModerationService()

def load_custom_nlp_service(container):
    nlp_service = OpenAINLPService()
    container[OpenAINLPService] = nlp_service
    container.get_moderation_service = nlp_service.get_moderation_service
    container.get_embedder = nlp_service.get_embedder
    container.get_schematic_generator = nlp_service.get_schematic_generator
    return container

# ===============================
# 4. Define Agent
# ===============================
async def create_agent(server: p.Server):
    agent = await server.create_agent(
        name="NREGA Assistant",
        description="Helps users understand NREGA eligibility, benefits, and application steps."
    )

    await agent.create_guideline(
            condition="Customer greets (hello, hi, namaste, good morning, etc.)",
            action="Respond with a warm greeting in their language. Thank them for connecting with PRAGATI and offer help with NREGA, PM-Kisan, or other schemes."
        )

    return agent

# ===============================
# 5. Main Server
# ===============================
async def main():
    async with p.Server() as server:
        agent = await create_agent(server)

        print("NREGA Assistant is running...")
        print("Agent created successfully!")
        print(f"Agent name: {agent.name}")
        print(f"Agent description: {agent.description}")

        print("\nTesting agent interaction...")

        try:
            customer = await server.create_customer(name="Test User")
            print(f"Created customer: {customer.name}")
        except Exception as e:
            print(f"Error creating customer: {e}")

        try:
            retrieved_agent = await server.get_agent()
            print(f"Retrieved agent: {retrieved_agent.name}")
        except Exception as e:
            print(f"Error retrieving agent: {e}")

if __name__ == "__main__":
    asyncio.run(main())