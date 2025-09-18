from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import PlainTextResponse

import os
import logging

# # Load environment variables
# load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Twilio Inbound Call Handler",
    description="FastAPI server for handling Twilio inbound calls",
    version="1.0.0"
)


@app.get("/")
async def root():
    """Health check endpoint"""
    return {"message": "Twilio Inbound Call Handler is running", "status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", 8000))
    debug = os.getenv("DEBUG", "False").lower() == "true"
    
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=debug,
        log_level="info"
    )
