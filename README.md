# Pipecat Twilio Inbound AI Agent

## Code & Config

```
twilio-pipecat-bot/
├── bot.py                   # TwilioBot + MetricsCollector
├── server.py                # FastAPI server + WebSocket endpoint
├── templates/
│   └── streams.xml          # TwiML for Twilio <Stream>
├── requirements.txt         # All Python dependencies
├── .env                     # API keys (Twilio, OpenAI, Deepgram, Cartesia)
├── call_stress_test.py      # Script to trigger 100 concurrent calls
├── constants.py             # VECTOR_DB, any other constants
└── README.md                # Setup & run instructions
```

## Installation

```console
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

In this project's directory, run the following command to copy the `.env.example` file to `.env`:

```console
cp .env.example .env
```

Edit the `.env` file with your own values.

### 1. **Start ngrok**:

In a new terminal, start ngrok to tunnel the local server:

```sh
ngrok http 8000
```

### 2. **Update the Twilio Webhook**:

- Go to your Twilio phone number's configuration page
- Under "Voice Configuration", in the "A call comes in" section:
  - Select "Webhook" from the dropdown
  - Enter your ngrok URL (e.g., http://<ngrok_url>)
  - Ensure "HTTP POST" is selected
- Click Save at the bottom of the page

### 3. **Configure streams.xml**:

- In `templates/streams.xml`, replace `2cee34967111.ngrok-free.app` with your ngrok URL (without `https://`)
- The final URL should look like: `wss://abc123.ngrok.io/ws`

### 4. **Run the FastAPI application**:

```sh
# Make sure you’re in the project directory and your virtual environment is activated
python server.py
```

### 5. **Trigger 100 test calls together**

```bash
python call_stress_test.py
```

### 6. **Check metrics**

```bash
curl http://localhost:8000/metrics // Some things need to be fixed here. but you can see all the processing in the console.
```

## Architecture & Trade-Offs

### 1. High-level System Architecture

```
[Twilio PSTN]
     │
     ▼
[Twilio <Stream> Webhook]
     │
     ▼
[FastAPI /ws WebSocket] <─┐
     │                     │
     ▼                     │
[Pipecat Pipeline]          │
 ├─ Audio Input (WebSocket) │
 ├─ STT (Deepgram)          │
 ├─ LLM (OpenAI)            │
 ├─ TTS (Cartesia)          │
 └─ Audio Output (WebSocket)│
```

---

### 2. Call Flow (Media & Control)

```
1. Twilio places call → webhook to FastAPI
2. FastAPI accepts WebSocket → starts Pipecat pipeline
3. User speaks → Silero VAD → Deepgram STT
4. Transcript → OpenAI LLM → response text
5. Response text → Cartesia TTS → audio frames
6. Audio frames → WebSocket → Twilio → User hears response
7. Metrics collected: jitter, packet loss, RTT
```

---

### 3. Scaling Plan

| Component             | Scaling Strategy                                                 |
| --------------------- | ---------------------------------------------------------------- |
| FastAPI server        | Multiple Uvicorn workers behind Nginx / Load Balancer            |
| WebSocket connections | Partition across multiple workers or nodes                       |
| STT / TTS / LLM       | Pool API requests, batch, or async streaming                     |
| MetricsCollector      | Centralized store (Redis/InfluxDB) instead of per-process memory |

---

### 4. Pipecat and Livekit Pros and cons

### Pipecat (purpose-built for voice AI)

**Pros**

- Designed for **AI-first voice use cases** (handles STT → LLM → TTS loop natively).
- Have integrations with major LLM, TTS and STT provider
- Good for Protoyping and faster project development
- Built-in session & agent management.

**Cons**

- Less mature ecosystem compared to LiveKit (newer, fewer battle-tested deployments).
- Less control over **raw audio streaming** and event handling.
- Scaling large concurrent real-time sessions may require **custom infra hacks** (distributed event bus, Redis/Kafka).

### LiveKit (real-time infra for voice/video)

**Pros**

- Natively for WebRTC and Real Communication Projects.
- Handles **scaling of WebSocket/WebRTC** connections better.
- More control over **audio pipeline** — you can insert your own STT/TTS/LLM workers.
- Strong ecosystem + **production deployments** (conferences, calls, customer support).
- Easier to scale horizontaly through autoscaling, geo-distributed.

**Cons**

- Not AI-specific.
- Slower prototyping (you’re closer to raw infra).
- Costs more engineering hours to maintain the “AI loop.”

---

## **1-Pager: 1,000 Calls & Bottlenecks**

**What would break at 1,000 calls?**

- Single-process FastAPI cannot handle 1,000 concurrent WebSockets
- Memory usage for 1,000 pipelines (LLM + TTS + Audio buffer)
- API rate limits for OpenAI / TTS / STT

**How to fix it**

- Use **multiple FastAPI workers / containers**
- Centralize metrics (Redis/InfluxDB)
- Pool / batch requests to STT/TTS with increased concurrent limits

**Where is latency bottleneck today?**

- STT → LLM → TTS pipeline
- LLM response generation (~100–300ms per short prompt)
- Network round-trip to Cartesia or OpenAI endpoints
- The distance between the user and the our server. Greater the distance, higher the latency.
