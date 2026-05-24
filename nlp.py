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

import re

def parse_intent(text: str) -> dict:
    """
    Parses a user's natural language text and returns a structured intent.
    Supported actions:
    - send: { "action": "send", "amount": <float>, "currency": "USDC", "recipient": "<name or address>" }
    - save_contact: { "action": "save_contact", "name": "<name>", "address": "<address>" }
    - tip: { "action": "tip", "amount": <float>, "currency": "USDC" }
    - unknown: { "action": "unknown", "message": "..." }
    """
    # 1. Quick regex fallback for perfect accuracy on common commands
    text_lower = text.lower().strip()
    
    # Match: save 0x... as name
    save_match = re.search(r"save(?: address)?\s+(0x[a-fA-F0-9]{40})\s+(?:as|for)?\s*(\w+)", text, re.IGNORECASE)
    if save_match:
        return {"action": "save_contact", "address": save_match.group(1), "name": save_match.group(2).lower()}
        
    # Match: pay 5 to 0x...
    pay_match = re.search(r"(?:pay|send)\s+([0-9.]+)(?:\s*usdc)?\s*(?:to)?\s*(0x[a-fA-F0-9]{40}|\w+)", text, re.IGNORECASE)
    if pay_match:
        return {"action": "send", "amount": float(pay_match.group(1)), "currency": "USDC", "recipient": pay_match.group(2).lower()}
        
    # Match: tip 5
    tip_match = re.search(r"(?:tip)\s+([0-9.]+)", text, re.IGNORECASE)
    if tip_match:
        return {"action": "tip", "amount": float(tip_match.group(1)), "currency": "USDC"}

    # 2. DeepSeek AI parsing for complex commands
    system_prompt = """You are a natural language parser for a crypto payment bot on Telegram.
The user wants to either save a contact address, send crypto (USDC) to someone, or tip someone in a group chat.
Extract the intent and output ONLY raw JSON, with no markdown formatting.

Possible JSON outputs:
1. {"action": "send", "amount": 10.5, "currency": "USDC", "recipient": "david"}
2. {"action": "save_contact", "name": "david", "address": "0x1234567890abcdef1234567890abcdef12345678"}
3. {"action": "tip", "amount": 5.0, "currency": "USDC"}
4. {"action": "unknown"}

Rules:
- If the user says "save 0x... johnny" or "save address 0x... for david", output save_contact.
- If the user says "send 10 usdc to david" or "pay 5 to 0x...", output send.
- If the user says "tip 5 usdc" or "send 5 usdc as a tip", output tip.
- Be highly flexible with typos. If the intent is obvious, extract it.
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

