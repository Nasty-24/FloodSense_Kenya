"""Step 2 check: does our API key reach Gemma 4 through the Gemini API?

    .venv\\Scripts\\python check_gemma.py
"""

import os

from dotenv import load_dotenv
from google import genai

load_dotenv()
model = os.getenv("GEMMA_MODEL", "gemma-4-26b-a4b-it")
client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
reply = client.models.generate_content(model=model, contents="Sema 'habari' kwa neno moja.")
print(f"{model} replied: {reply.text}")
