# Twilio Inbound Call Handler

A FastAPI-based server for handling inbound calls through Twilio. This application provides webhook endpoints to process incoming calls, gather user input, and route calls appropriately.

## Features

- **Inbound Call Handling**: Process incoming calls from Twilio
- **Interactive Voice Response (IVR)**: Menu system with digit input
- **Call Routing**: Route calls to different departments (Sales, Support, Operator)
- **Recording**: Record voicemail messages
- **Status Tracking**: Monitor call status updates
- **Health Checks**: Built-in health monitoring endpoints

## Setup

### 1. Install Dependencies

Make sure you have Python 3.8+ installed and activate your virtual environment:

```bash
# Activate virtual environment (if not already activated)
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Environment Configuration

Copy the example environment file and configure your Twilio credentials:

```bash
cp env.example .env
```

Edit the `.env` file with your Twilio credentials:

```env
# Twilio Configuration
TWILIO_ACCOUNT_SID=your_account_sid_here
TWILIO_AUTH_TOKEN=your_auth_token_here
TWILIO_PHONE_NUMBER=your_twilio_phone_number_here

# Server Configuration
HOST=0.0.0.0
PORT=8000
DEBUG=True
```

### 3. Run the Server

You can run the server in several ways:

**Option 1: Using the run script**

```bash
python run.py
```

**Option 2: Using uvicorn directly**

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

**Option 3: Using the main module**

```bash
python main.py
```

The server will start on `http://localhost:8000` by default.

## API Endpoints

### Health Check

- `GET /` - Basic health check
- `GET /health` - Detailed health status

### Twilio Webhooks

- `POST /webhook/voice` - Handle incoming calls
- `POST /webhook/gather` - Process user input
- `POST /webhook/operator` - Handle operator transfer
- `POST /webhook/recording` - Process recorded messages
- `POST /webhook/status` - Handle call status updates

## Twilio Configuration

### 1. Set up your Twilio Phone Number

1. Log into your [Twilio Console](https://console.twilio.com/)
2. Go to Phone Numbers → Manage → Active numbers
3. Click on your phone number
4. Set the webhook URL for incoming calls to: `https://your-domain.com/webhook/voice`
5. Set the webhook URL for call status to: `https://your-domain.com/webhook/status`

### 2. For Local Development

Use ngrok or similar tool to expose your local server:

```bash
# Install ngrok (if not already installed)
# Download from https://ngrok.com/

# Expose your local server
ngrok http 8000
```

Then use the ngrok URL in your Twilio webhook configuration.

## API Documentation

Once the server is running, you can access the interactive API documentation at:

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Call Flow

1. **Incoming Call**: Twilio sends a webhook to `/webhook/voice`
2. **Greeting**: Caller hears a greeting message
3. **Menu**: Caller is prompted to press 1 for sales, 2 for support, or 0 for operator
4. **Routing**: Based on input, call is routed to appropriate handler
5. **Recording**: If no operator is available, caller can leave a message
6. **Status Updates**: Call status is tracked via `/webhook/status`

## Customization

### Adding New Menu Options

Edit the `handle_inbound_call` function in `main.py` to add new menu options:

```python
gather.say("Press 1 for sales, press 2 for support, press 3 for billing, or press 0 to speak with an operator.")
```

Then update the `handle_gather` function to process the new option:

```python
elif digits == "3":
    response.say("Thank you for choosing billing. Our billing team will assist you.")
```

### Customizing Voice and Language

You can customize the voice and language in the TwiML responses:

```python
response.say("Hello! Thank you for calling.", voice="alice", language="en-US")
```

## Error Handling

The application includes comprehensive error handling:

- Webhook validation
- Twilio API error handling
- Logging for debugging
- Graceful fallbacks for failed operations

## Logging

Logs are written to the console with different levels:

- INFO: Normal operations
- WARNING: Non-critical issues
- ERROR: Errors that need attention

## Development

### Running in Development Mode

Set `DEBUG=True` in your `.env` file to enable:

- Auto-reload on code changes
- Detailed error messages
- Debug logging

### Testing Webhooks Locally

Use tools like ngrok, localtunnel, or similar to expose your local server for Twilio webhook testing.

## Production Deployment

For production deployment:

1. Set `DEBUG=False` in your environment
2. Use a production ASGI server like Gunicorn with Uvicorn workers
3. Set up proper logging
4. Use environment variables for sensitive configuration
5. Set up monitoring and health checks

## License

This project is open source and available under the MIT License.
