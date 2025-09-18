# Pipecat Twilio AI Agent

This project is a FastAPI-based chatbot that integrates with Twilio to handle WebSocket connections and provide real-time communication. The project includes endpoints for starting a call and handling WebSocket connections.
Customize the bot.py file to change the AI agent's behavior.
This is setup to save audio recordings to the server_0_recording.wav file.

## Installation

```console
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Install ngrok: Follow the instructions on the [ngrok website](https://ngrok.com/download) to download and install ngrok.

## Setup Environment

In this project's directory, run the following command to copy the `.env.example` file to `.env`:

```console
cp .env.example .env
```

Edit the `.env` file with your own values.

## Configure Twilio URLs

1. **Start ngrok**:
   In a new terminal, start ngrok to tunnel the local server:

   ```sh
   ngrok http 8000
   ```

2. **Update the Twilio Webhook**:

   - Go to your Twilio phone number's configuration page
   - Under "Voice Configuration", in the "A call comes in" section:
     - Select "Webhook" from the dropdown
     - Enter your ngrok URL (e.g., http://<ngrok_url>)
     - Ensure "HTTP POST" is selected
   - Click Save at the bottom of the page

3. **Configure streams.xml**:
   - In `templates/streams.xml`, replace `2cee34967111.ngrok-free.app` with your ngrok URL (without `https://`)
   - The final URL should look like: `wss://abc123.ngrok.io/ws`

## Usage

**Run the FastAPI application**:

```sh
# Make sure you’re in the project directory and your virtual environment is activated
python server.py
```
