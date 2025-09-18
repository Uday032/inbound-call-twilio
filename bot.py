#
# Copyright (c) 2025, Daily
#
# SPDX-License-Identifier: BSD 2-Clause License
#

import datetime
import io
import os
import sys
import wave

import aiofiles
from dotenv import load_dotenv
from fastapi import WebSocket
from loguru import logger

from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.aggregators.openai_llm_context import OpenAILLMContext
from pipecat.processors.audio.audio_buffer_processor import AudioBufferProcessor
from pipecat.serializers.twilio import TwilioFrameSerializer
from pipecat.services.elevenlabs.tts import ElevenLabsTTSService
from pipecat.services.cartesia.tts import CartesiaTTSService
from pipecat.services.deepgram.stt import DeepgramSTTService
from pipecat.services.openai.llm import OpenAILLMService
from pipecat.transports.network.fastapi_websocket import (
    FastAPIWebsocketParams,
    FastAPIWebsocketTransport,
)
from pipecat.audio.vad.vad_analyzer import VADParams

load_dotenv(override=True)

logger.remove(0)
logger.add(sys.stderr, level="DEBUG")

class TwilioBot:
    def __init__(self):
        self.default_system_message = {
            "role": "system",
            "content": "You are a helpful assistant named Tasha. Your output will be converted to audio so don't include special characters in your answers. Respond with a short short sentence.",
        }

    async def run(self, websocket_client: WebSocket, stream_sid: str, testing: bool):
        transport = FastAPIWebsocketTransport(
            websocket=websocket_client,
            params=FastAPIWebsocketParams(
                audio_in_enabled=True,
                audio_out_enabled=True,
                add_wav_header=False,
                vad_enabled=True,
                vad_analyzer=SileroVADAnalyzer(params=VADParams(start_secs=0.15, stop_secs=0.2)),
                vad_audio_passthrough=True,
                serializer=TwilioFrameSerializer(stream_sid),
            ),
        )

        llm = OpenAILLMService(api_key=os.getenv("OPENAI_API_KEY"), model="gpt-4o-mini", max_tokens=64)

        stt = DeepgramSTTService(
            api_key=os.getenv("DEEPGRAM_API_KEY"),
            audio_passthrough=True,
            model="nova-2-phonecall",
            interim_results=True,
            punctuate=False,
            smart_format=False,
            endpointing=50 
        )

        tts = CartesiaTTSService(
            api_key=os.getenv("CARTESIA_API_KEY"),
            voice_id="71a7ad14-091c-4e8e-a314-022ece01c121",  # British Reading Lady
            stream=True  
        )

        messages = [self.default_system_message.copy()]

        context = OpenAILLMContext(messages)
        context_aggregator = llm.create_context_aggregator(context)

        # NOTE: Watch out! This will save all the conversation in memory. You can
        # pass `buffer_size` to get periodic callbacks.
        audiobuffer = AudioBufferProcessor(user_continuous_stream=not testing)

        pipeline = Pipeline(
            [
                transport.input(),  # Websocket input from client
                stt,  # Speech-To-Text
                context_aggregator.user(),
                llm,  # LLM
                tts,  # Text-To-Speech
                transport.output(),  # Websocket output to client
                audiobuffer,  # Used to buffer the audio in the pipeline
                context_aggregator.assistant(),
            ]
        )

        task = PipelineTask(
            pipeline,
            params=PipelineParams(
                audio_in_sample_rate=8000,
                audio_out_sample_rate=8000,
                allow_interruptions=True,
            ),
        )

        @transport.event_handler("on_client_connected")
        async def on_client_connected(transport, client):
            await audiobuffer.start_recording()
            messages.append({"role": "system", "content": "Please introduce yourself to the user."})
            await task.queue_frames([context_aggregator.user().get_context_frame()])

        @transport.event_handler("on_client_disconnected")
        async def on_client_disconnected(transport, client):
            await task.cancel()

        @audiobuffer.event_handler("on_audio_data")
        async def on_audio_data(buffer, audio, sample_rate, num_channels):
            server_name = f"server_{websocket_client.client.port}"

        runner = PipelineRunner(handle_sigint=False, force_gc=True)

        await runner.run(task)


# Backwards-compatible function for existing imports
async def run_bot(websocket_client: WebSocket, stream_sid: str, testing: bool):
    bot = TwilioBot()
    await bot.run(websocket_client, stream_sid, testing)