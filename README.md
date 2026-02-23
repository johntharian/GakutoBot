# 📚 StudyScroll

Turn any topic into a scroll-friendly study feed with audio — inside Telegram.

```
User sends topic → Claude generates cards → Audio is created → Mini App opens in Telegram
```

---

## Architecture

```
study-scroll/
├── bot/
│   └── main.py           # Telegram bot — receives topics, sends Mini App button
├── generator/
│   ├── content.py        # Claude API → structured JSON study cards
│   └── audio.py          # gTTS → MP3 audio summary
├── api/
│   └── server.py         # FastAPI — serves session data, audio, and the webapp
├── webapp/
│   └── index.html        # The scroll feed Mini App UI (served by FastAPI)
├── storage/
│   └── sessions/         # Per-session .json and .mp3 files
├── run.py                # Starts API + bot together
├── requirements.txt
└── .env.example
```

---

## Setup

### 1. Clone and install dependencies

```bash
git clone <your-repo>
cd study-scroll
pip install -r requirements.txt
```

### 2. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env`:

```env
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
ANTHROPIC_API_KEY=your_anthropic_api_key_here
GEMINI_API_KEY=your_gemini_api_key_here
WEBAPP_BASE_URL=https://your-domain.com
```

### 3. Get a Telegram Bot Token

1. Open Telegram and message [@BotFather](https://t.me/BotFather)
2. Send `/newbot` and follow the prompts
3. Copy the token into `.env`

### 4. Deploy the server (required for Telegram Mini Apps)

Telegram Mini Apps **must** be served over HTTPS. Deploy to one of these for free:

**Render (recommended)**
1. Push your code to GitHub
2. Create a new Web Service on [render.com](https://render.com)
3. Set build command: `pip install -r requirements.txt`
4. Set start command: `python run.py`
5. Add your environment variables in the Render dashboard
6. Your URL will be `https://your-app-name.onrender.com`

**Railway**
```bash
railway up
```

**Fly.io**
```bash
flyctl launch
flyctl deploy
```

### 5. Register the Mini App with BotFather

1. Message [@BotFather](https://t.me/BotFather)
2. Send `/newapp`
3. Select your bot
4. Set the Web App URL to your deployed server URL (e.g. `https://your-app.onrender.com`)

### 6. Update WEBAPP_BASE_URL

Set `WEBAPP_BASE_URL` in your `.env` (and in your hosting dashboard) to your deployed HTTPS URL.

### 7. Run locally (for development)

```bash
python run.py
```

For local development with Telegram Mini Apps, you need HTTPS. Use [ngrok](https://ngrok.com):

```bash
ngrok http 8000
# Copy the https URL and set it as WEBAPP_BASE_URL in .env
```

---

## How It Works

1. **User sends a message** to the bot with any topic
2. **Bot calls LLM** (Gemini or Claude) which returns 12-18 structured study cards as JSON
3. **Bot generates audio** using gTTS (text-to-speech) from the card content
4. **Session is saved** as `{session_id}.json` and `{session_id}.mp3`
5. **Bot replies** with an inline button that opens the Mini App
6. **Mini App loads** the cards and renders them as a scroll feed with:
   - Color-coded card types (concept, analogy, example, quiz, summary)
   - Tap-to-reveal quiz cards
   - Scroll progress bar
   - Sticky audio player with speed control (1×, 1.25×, 1.5×, 2×)

---

## Card Types

| Type | Purpose | Color |
|------|---------|-------|
| 📌 Concept | Core definition | Purple |
| 🔗 Analogy | Relates to something familiar | Teal |
| 💡 Example | Real-world application | Green |
| 🔬 Deep Dive | Extra depth | Orange |
| 🧠 Quiz | Tap to reveal answer | Pink |
| ✅ Summary | End recap | Purple |

---

## Upgrading Audio Quality

The default TTS is gTTS (free, decent quality). To upgrade:

**ElevenLabs** (best quality):
```python
# In generator/audio.py
# Replace gTTS with ElevenLabs API call
```

**OpenAI TTS** (great quality):
```python
from openai import OpenAI
client = OpenAI()
response = client.audio.speech.create(model="tts-1", voice="alloy", input=script)
response.stream_to_file(output_path)
```

---

## Example Topics

- "How does the immune system work?"
- "Explain supply and demand"
- "The French Revolution"
- "Basics of Python decorators"
- "What is quantum entanglement?"
- "How does a neural network learn?"
