import asyncio
import os
from gtts import gTTS


async def generate_audio(script: str, output_path: str) -> str:
    """Generate an MP3 audio file from a text script using gTTS."""

    def _synthesize():
        tts = gTTS(text=script, lang="en", slow=False)
        tts.save(output_path)

    # gTTS is synchronous, run in thread pool to avoid blocking
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _synthesize)

    return output_path
