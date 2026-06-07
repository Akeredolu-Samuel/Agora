import os
import json
import re
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
    - send:         { "action": "send", "amount": <float>, "currency": "USDC", "recipient": "<name or address>" }
    - save_contact: { "action": "save_contact", "name": "<name>", "address": "<address>" }
    - tip:          { "action": "tip", "amount": <float>, "currency": "USDC" }
    - swap:         { "action": "swap", "amount": <float>, "from_token": "USDC", "to_token": "EURC" }
    - unknown:      { "action": "unknown" }
    """
    text_lower = text.lower().strip()

    # --- Quick regex fallbacks (fast, zero AI cost) ---

    # save 0x... as name
    save_match = re.search(
        r"save(?:\s+address)?\s+(0x[a-fA-F0-9]{40})\s+(?:as|for)?\s*(\w+)",
        text, re.IGNORECASE
    )
    if save_match:
        return {"action": "save_contact", "address": save_match.group(1), "name": save_match.group(2).lower()}

    # pay/send 5 usdc to david / 0x...
    pay_match = re.search(
        r"(?:pay|send)\s+([0-9.]+)(?:\s*usdc)?\s*(?:to)?\s*(0x[a-fA-F0-9]{40}|\w+)",
        text, re.IGNORECASE
    )
    if pay_match:
        return {"action": "send", "amount": float(pay_match.group(1)), "currency": "USDC",
                "recipient": pay_match.group(2).lower()}

    # tip 5
    tip_match = re.search(r"(?:tip)\s+([0-9.]+)", text, re.IGNORECASE)
    if tip_match:
        return {"action": "tip", "amount": float(tip_match.group(1)), "currency": "USDC"}

    # swap 10 usdc for/to eurc
    swap_match = re.search(
        r"swap\s+([0-9.]+)\s*(\w+)\s+(?:for|to)\s*(\w+)",
        text, re.IGNORECASE
    )
    if swap_match:
        return {
            "action":     "swap",
            "amount":     float(swap_match.group(1)),
            "from_token": swap_match.group(2).upper(),
            "to_token":   swap_match.group(3).upper(),
        }

    # --- DeepSeek AI fallback for complex / typo-heavy commands ---
    system_prompt = """You are a natural language parser for a crypto payment Telegram bot.
The user wants to send, save, tip, or swap tokens.
Output ONLY raw JSON — no markdown, no explanation.

Possible JSON outputs:
1. {"action": "send", "amount": 10.5, "currency": "USDC", "recipient": "david"}
2. {"action": "save_contact", "name": "david", "address": "0x1234567890abcdef1234567890abcdef12345678"}
3. {"action": "tip", "amount": 5.0, "currency": "USDC"}
4. {"action": "swap", "amount": 10.0, "from_token": "USDC", "to_token": "EURC"}
5. {"action": "unknown"}

Rules:
- "save 0x... as john" → save_contact
- "send/pay 10 usdc to david" → send
- "tip 5 usdc" → tip
- "swap 10 usdc for eurc" / "exchange 5 usdc to eurc" → swap
- Be highly flexible with typos. If the intent is obvious, extract it.
"""
    try:
        response = _get_client().chat.completions.create(
            model="deepseek/deepseek-chat",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": text}
            ],
            temperature=0.0
        )
        content = response.choices[0].message.content.strip()
        # Strip markdown code fences if model wraps output
        content = re.sub(r"^```(?:json)?\s*", "", content)
        content = re.sub(r"\s*```$", "", content)
        return json.loads(content.strip())
    except Exception as e:
        print(f"Error parsing intent: {e}")
        return {"action": "unknown"}
