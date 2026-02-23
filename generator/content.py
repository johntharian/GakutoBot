import anthropic
from google import genai
from google.genai import types
import json
import os

anthropic_client = None
if os.getenv("ANTHROPIC_API_KEY"):
    anthropic_client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

gemini_client = None
if os.getenv("GEMINI_API_KEY"):
    gemini_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

SYSTEM_PROMPT = """You are a brilliant tutor who turns any topic into an engaging, scroll-friendly study feed.

Generate a JSON array of study cards. Each card should be short, punchy, and digestible — like a smart social feed, not a textbook.

Card types and their schemas:
- concept:   { "type": "concept",   "title": str, "body": str }
- analogy:   { "type": "analogy",   "title": str, "body": str }
- example:   { "type": "example",   "title": str, "body": str }
- deep_dive: { "type": "deep_dive", "title": str, "body": str }
- quiz:      { "type": "quiz",      "question": str, "answer": str }
- summary:   { "type": "summary",   "title": str, "body": str }

Rules:
- Generate 12-18 cards per topic
- Each body/answer must be under 120 words
- Start with a "concept" card that defines the topic clearly
- Sprinkle in 2-3 "quiz" cards throughout (not all at the end)
- End with a "summary" card
- Write like you're explaining to a curious 20-year-old, not a professor
- Use concrete language, no fluff

Return ONLY valid JSON array. No markdown, no explanation, no code fences."""


async def generate_study_cards(topic: str) -> list[dict]:
    """Call an LLM and return a list of structured study cards."""
    # Prefer Gemini if configured, otherwise fallback to Anthropic
    if gemini_client:
        response = gemini_client.models.generate_content(
            model='gemini-2.5-flash',
            contents=f"Create a study feed for this topic: {topic}",
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                response_mime_type="application/json",
            ),
        )
        raw = response.text.strip()
    elif anthropic_client:
        message = anthropic_client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": f"Create a study feed for this topic: {topic}"
                }
            ]
        )
        raw = message.content[0].text.strip()
    else:
        raise ValueError("No LLM API keys configured. Set GEMINI_API_KEY or ANTHROPIC_API_KEY.")

    # Strip accidental markdown fences if LLM wraps them (mostly for Anthropic)
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]

    cards = json.loads(raw)
    return cards


def cards_to_audio_script(topic: str, cards: list[dict]) -> str:
    """Convert cards into a natural spoken script for TTS."""
    lines = [f"Let's study {topic}.\n"]

    for card in cards:
        ctype = card.get("type")

        if ctype == "quiz":
            lines.append(f"Quiz time. {card['question']} ... Think about it ... The answer is: {card['answer']}")
        elif ctype == "summary":
            lines.append(f"Summary. {card['title']}. {card['body']}")
        else:
            lines.append(f"{card['title']}. {card['body']}")

    return "\n\n".join(lines)
