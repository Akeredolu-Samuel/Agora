import os
import json
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

_client = None

def _get_client():
    global _client
    if _client is None:
        _client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=os.getenv("OPENROUTER_API_KEY"),
        )
    return _client

def parse_intent(text: str) -> dict:
    """
    Parses a user's natural language text and returns a structured intent.
    Supported actions:
    - send: { "action": "send", "amount": <float>, "currency": "USDC", "recipient": "<name or address>" }
    - save_contact: { "action": "save_contact", "name": "<name>", "address": "<address>" }
    - unknown: { "action": "unknown", "message": "..." }
    """
    system_prompt = """You are a natural language parser for a crypto payment bot on Telegram.
The user wants to either save a contact address or send crypto (USDC) to someone.
Extract the intent and output ONLY raw JSON, with no markdown formatting.

Possible JSON outputs:
1. {"action": "send", "amount": 10.5, "currency": "USDC", "recipient": "david"}
2. {"action": "save_contact", "name": "david", "address": "0x1234567890abcdef1234567890abcdef12345678"}
3. {"action": "unknown"}

If the user says something like "save address 0xabc for david", output save_contact.
If the user says "send 10 usdc to david", output send.
"""
    try:
        response = _get_client().chat.completions.create(
            model="deepseek/deepseek-chat",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text}
            ],
            temperature=0.0
        )
        content = response.choices[0].message.content.strip()
        # Clean up in case DeepSeek adds markdown blocks
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        return json.loads(content.strip())
    except Exception as e:
        print(f"Error parsing intent: {e}")
        return {"action": "unknown"}

