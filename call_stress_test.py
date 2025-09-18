# call_stress_test.py
import os
import asyncio
from twilio.rest import Client

TWILIO_ACCOUNT_SID = os.environ["TWILIO_ACCOUNT_SID"]
TWILIO_AUTH_TOKEN  = os.environ["TWILIO_AUTH_TOKEN"]

FROM_NUMBER = os.environ["TWILIO_FROM_NUMBER"]   # your Twilio number
TO_NUMBER   = os.environ["TWILIO_TO_NUMBER"]     # the same Twilio number that triggers your bot
TWIML_APP_URL = "https://2cee34967111.ngrok-free.app"    # must return valid TwiML (<Response><Stream>...</Response>)

client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

async def place_call(i):
    """
    Place a single outbound call via Twilio REST API.
    """
    try:
        call = client.calls.create(
            to=TO_NUMBER,
            from_=FROM_NUMBER,
            url=TWIML_APP_URL,   # Twilio fetches TwiML from here
            method="POST",
        )
        print(f"Call {i} SID: {call.sid}")
    except Exception as e:
        print(f"Call {i} failed: {e}")

async def main(concurrent_calls: int = 100):
    tasks = [asyncio.to_thread(place_call, i) for i in range(concurrent_calls)]
    await asyncio.gather(*tasks)

if __name__ == "__main__":
    asyncio.run(main(100))