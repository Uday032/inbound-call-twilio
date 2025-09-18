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
from time import perf_counter

from constants import VECTOR_DB


class MetricsCollector:
    def __init__(self):
        self.jitter_ms_sum = 0.0
        self.jitter_samples = 0
        self.packets_expected = 0
        self.packets_received = 0
        self.prev_audio_arrival_ts = None
        self.prev_audio_duration_ms = None

        self.response_latencies_ms = []
        self.awaiting_tts_after_user = False
        self.user_utterance_done_ts = None

        self.calls_attempted = 0
        self.calls_established = 0

    def record_call_attempt(self):
        self.calls_attempted += 1

    def record_call_established(self):
        self.calls_established += 1

    def mark_user_utterance_completed(self):
        self.user_utterance_done_ts = perf_counter()
        self.awaiting_tts_after_user = True

    def record_tts_audio_chunk(self, bytes_count: int, sample_rate: int, num_channels: int):
        now = perf_counter()
        bytes_per_sample = 2
        samples = bytes_count / (bytes_per_sample * max(1, num_channels))
        duration_ms = (samples / max(1, sample_rate)) * 1000.0

        if self.prev_audio_arrival_ts is not None and self.prev_audio_duration_ms is not None:
            gap_ms = (now - self.prev_audio_arrival_ts) * 1000.0
            expected_ms = self.prev_audio_duration_ms
            missing = 0
            if expected_ms > 1.0:
                missing = int(max(0, (gap_ms - expected_ms) // expected_ms))
            self.packets_expected += 1 + missing
            self.packets_received += 1
            jitter_ms = abs(gap_ms - expected_ms)
            self.jitter_ms_sum += jitter_ms
            self.jitter_samples += 1
        else:
            self.packets_expected += 1
            self.packets_received += 1

        if self.awaiting_tts_after_user and self.user_utterance_done_ts is not None:
            rtt_ms = (now - self.user_utterance_done_ts) * 1000.0
            self.response_latencies_ms.append(rtt_ms)
            self.awaiting_tts_after_user = False
            self.user_utterance_done_ts = None

        self.prev_audio_arrival_ts = now
        self.prev_audio_duration_ms = duration_ms

    def get_metrics(self):
        jitter_avg_ms = (self.jitter_ms_sum / self.jitter_samples) if self.jitter_samples else 0.0
        packet_loss_rate = 0.0
        if self.packets_expected > 0:
            lost = max(0, self.packets_expected - self.packets_received)
            packet_loss_rate = lost / float(self.packets_expected)

        mos = max(1.0, min(4.5, 4.5 - 10.0 * packet_loss_rate - (jitter_avg_ms / 100.0)))

        latencies = sorted(self.response_latencies_ms)
        avg_latency_ms = (sum(latencies) / len(latencies)) if latencies else 0.0
        p95_index = int(0.95 * (len(latencies) - 1)) if latencies else 0
        p95_latency_ms = latencies[p95_index] if latencies else 0.0

        failed_setup_rate = 0.0
        if self.calls_attempted > 0:
            failed_setup_rate = (self.calls_attempted - self.calls_established) / float(self.calls_attempted)

        return {
            "jitter_ms_avg": jitter_avg_ms,
            "packet_loss_rate": packet_loss_rate,
            "mos_estimate": mos,
            "agent_response_time_ms_avg": avg_latency_ms,
            "agent_response_time_ms_p95": p95_latency_ms,
            "failed_call_setup_rate": failed_setup_rate,
            "calls_attempted": self.calls_attempted,
            "calls_established": self.calls_established,
        }

load_dotenv(override=True)

logger.remove(0)
logger.add(sys.stderr, level="DEBUG")

class TwilioBot:
    def __init__(self, metrics: MetricsCollector | None = None):
        self.default_system_message = {
            "role": "system",
            "content": "You are a helpful assistant named Tasha. Your output will be converted to audio so don't include special characters in your answers. Respond with a short short sentence. Here is more details to answer user questions: "+ VECTOR_DB,
        }
        self.metrics = metrics or MetricsCollector()

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
            self.metrics.record_call_established()
            await audiobuffer.start_recording()
            messages.append({"role": "system", "content": "Please introduce yourself to the user."})
            await task.queue_frames([context_aggregator.user().get_context_frame()])

        @transport.event_handler("on_client_disconnected")
        async def on_client_disconnected(transport, client):
            await task.cancel()

        

        @stt.event_handler("on_transcript")
        async def on_transcript(service, result):
            # Be more specific about what constitutes final transcript
            is_final = False
            print(service, is_final)
            # Check various possible final indicators
            if result.get("is_final", False):
                is_final = True
            elif result.get("final", False):
                is_final = True
            elif result.get("speech_final", False):
                is_final = True
            elif result.get("type") == "final":
                is_final = True
            
            # Also check if transcript has meaningful content
            transcript = result.get("transcript", "").strip()
            
            if is_final and transcript:
                logger.debug(f"STT final transcript detected: '{transcript}'; starting response latency timer")
                self.metrics.mark_user_utterance_completed()

        @audiobuffer.event_handler("on_audio_data")
        async def on_audio_data(buffer, audio, sample_rate, num_channels):
            if self.metrics.awaiting_tts_after_user or len(self.metrics.response_latencies_ms) == 0:
                self.metrics.record_tts_audio_chunk(len(audio), sample_rate, num_channels)

        @tts.event_handler("on_tts_started")
        async def on_tts_started(service):
            if self.metrics.awaiting_tts_after_user and self.metrics.user_utterance_done_ts is not None:
                now = perf_counter()
                rtt_ms = (now - self.metrics.user_utterance_done_ts) * 1000.0
                self.metrics.response_latencies_ms.append(rtt_ms)
                self.metrics.awaiting_tts_after_user = False
                logger.debug(f"TTS started - recorded response latency: {rtt_ms:.2f}ms")
                self.metrics.user_utterance_done_ts = None

        runner = PipelineRunner(handle_sigint=False, force_gc=True)

        await runner.run(task)



# Backwards-compatible function for existing imports
async def run_bot(websocket_client: WebSocket, stream_sid: str, testing: bool):
    bot = TwilioBot()
    await bot.run(websocket_client, stream_sid, testing)