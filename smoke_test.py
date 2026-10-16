"""Session smoke test: verifies .env loads and the Portkey gateway answers via PydanticAI."""
import os
from pathlib import Path

from dotenv import load_dotenv
from openai import AsyncOpenAI
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

HERE = Path(__file__).resolve().parent
load_dotenv(HERE / ".env")

key = os.getenv("PORTKEY_API_KEY")
if not key:
    raise SystemExit("PORTKEY_API_KEY missing from .env")

client = AsyncOpenAI(api_key=key, base_url="https://api.portkey.ai/v1", default_headers={"x-portkey-api-key": key})
model = OpenAIChatModel(os.getenv("OPENAI_MODEL", "gpt-6-luna"), provider=OpenAIProvider(openai_client=client))
joke = (HERE / "joke.txt").read_text()
result = Agent(model).run_sync(f"Reply with one short sentence rating this joke 1-10:\n\n{joke}")
print("OK:", result.output)
