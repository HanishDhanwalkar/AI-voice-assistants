"""
## Setup
```
pip install google-genai opencv-python pyaudio pillow mss
```
"""

import asyncio
import base64
import io
import traceback
import cv2
import pyaudio
import PIL.Image
import mss
import argparse
from google import genai
from google.genai import types

from dotenv import load_dotenv
import os
load_dotenv(".env")

GEMINI_API_KEY = os.environ.get("GEMINIAPIKEY")

FORMAT = pyaudio.paInt16
CHANNELS = 1
SEND_SAMPLE_RATE = 16000
RECEIVE_SAMPLE_RATE = 24000
CHUNK_SIZE = 1024

MODEL = "models/gemini-2.0-flash-live-001"

DEFAULT_MODE = "camera"
DEFAULT_PERSONA = "default"

# Define personas as system prompts
PERSONAS = {
    "default": "",
    "customer_care": """You are a helpful and friendly customer service representative. 
                      Your name is Alex. You speak in a polite, professional tone and use phrases like 
                      "How may I assist you today?", "I understand your concern", and "Let me help resolve that for you". 
                      You always thank the customer for their patience and ask if there's anything else you can help with.""",
    "tech_support": """You are a technical support specialist named Taylor.
                     You use technical terminology when appropriate but explain concepts in simple terms when needed.
                     You're patient and methodical, walking users through troubleshooting steps one at a time.
                     You ask clarifying questions to better understand technical issues.""",
    "sales_agent": """You are a friendly sales representative named Jordan.
                     You're enthusiastic about products and focus on benefits rather than features.
                     You use persuasive language but are never pushy. You ask questions to understand 
                     customer needs before making recommendations.""",
    "fitness_coach": """You are a motivational fitness coach named Alex.
                      You're energetic and encouraging. You use phrases like "You can do this!", 
                      "Great work!", and "Let's push a bit further!". You give clear, concise instructions 
                      and provide modifications for different fitness levels."""
}

client = genai.Client(
    http_options={"api_version": "v1beta"},
    api_key=GEMINI_API_KEY
)


class AudioLoop:
    def __init__(self, video_mode=DEFAULT_MODE, persona=DEFAULT_PERSONA, voice="Puck"):
        self.video_mode = video_mode
        self.persona = persona
        self.voice = voice
        
        # Create PyAudio instance for this object
        self.pya_instance = pyaudio.PyAudio()

        self.audio_in_queue = None
        self.out_queue = None

        self.session = None
        self.audio_stream = None

        self.send_text_task = None
        self.receive_audio_task = None
        self.play_audio_task = None
        
        # Configure the response modalities and voice
        self.config = types.LiveConnectConfig(
            response_modalities=["audio"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=self.voice)
                )
            ),
        )
        
        # No direct system_prompt property, we'll handle this differently

    async def send_text(self):
        while True:
            text = await asyncio.to_thread(
                input,
                "message > ",
            )
            if text.lower() == "q":
                break
            await self.session.send(input=text or ".", end_of_turn=True)

    def _get_frame(self, cap):
        # Read the frame
        ret, frame = cap.read()
        # Check if the frame was read successfully
        if not ret:
            return None
        # Fix: Convert BGR to RGB color space
        # OpenCV captures in BGR but PIL expects RGB format
        # This prevents the blue tint in the video feed
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img = PIL.Image.fromarray(frame_rgb)  # Now using RGB frame
        img.thumbnail([1024, 1024])

        image_io = io.BytesIO()
        img.save(image_io, format="jpeg")
        image_io.seek(0)

        mime_type = "image/jpeg"
        image_bytes = image_io.read()
        return {"mime_type": mime_type, "data": base64.b64encode(image_bytes).decode()}

    async def get_frames(self):
        # This takes about a second, and will block the whole program
        # causing the audio pipeline to overflow if you don't to_thread it.
        cap = await asyncio.to_thread(
            cv2.VideoCapture, 0
        )  # 0 represents the default camera

        while True:
            frame = await asyncio.to_thread(self._get_frame, cap)
            if frame is None:
                break

            await asyncio.sleep(1.0)

            await self.out_queue.put(frame)

        # Release the VideoCapture object
        cap.release()

    def _get_screen(self):
        sct = mss.mss()
        monitor = sct.monitors[0]

        i = sct.grab(monitor)

        mime_type = "image/jpeg"
        image_bytes = mss.tools.to_png(i.rgb, i.size)
        img = PIL.Image.open(io.BytesIO(image_bytes))

        image_io = io.BytesIO()
        img.save(image_io, format="jpeg")
        image_io.seek(0)

        image_bytes = image_io.read()
        return {"mime_type": mime_type, "data": base64.b64encode(image_bytes).decode()}

    async def get_screen(self):
        while True:
            frame = await asyncio.to_thread(self._get_screen)
            if frame is None:
                break

            await asyncio.sleep(1.0)

            await self.out_queue.put(frame)

    async def send_realtime(self):
        while True:
            msg = await self.out_queue.get()
            await self.session.send(input=msg)

    async def listen_audio(self):
        mic_info = self.pya_instance.get_default_input_device_info()
        self.audio_stream = await asyncio.to_thread(
            self.pya_instance.open,
            format=FORMAT,
            channels=CHANNELS,
            rate=SEND_SAMPLE_RATE,
            input=True,
            input_device_index=mic_info["index"],
            frames_per_buffer=CHUNK_SIZE,
        )
        if __debug__:
            kwargs = {"exception_on_overflow": False}
        else:
            kwargs = {}
        while True:
            data = await asyncio.to_thread(self.audio_stream.read, CHUNK_SIZE, **kwargs)
            await self.out_queue.put({"data": data, "mime_type": "audio/pcm"})

    async def receive_audio(self):
        "Background task to reads from the websocket and write pcm chunks to the output queue"
        while True:
            turn = self.session.receive()
            async for response in turn:
                if data := response.data:
                    self.audio_in_queue.put_nowait(data)
                    continue
                if text := response.text:
                    print(text, end="")

            # If you interrupt the model, it sends a turn_complete.
            # For interruptions to work, we need to stop playback.
            # So empty out the audio queue because it may have loaded
            # much more audio than has played yet.
            while not self.audio_in_queue.empty():
                self.audio_in_queue.get_nowait()

    async def play_audio(self):
        stream = await asyncio.to_thread(
            self.pya_instance.open,
            format=FORMAT,
            channels=CHANNELS,
            rate=RECEIVE_SAMPLE_RATE,
            output=True,
        )
        while True:
            bytestream = await self.audio_in_queue.get()
            await asyncio.to_thread(stream.write, bytestream)

    async def run(self):
        try:            
            async with (
                client.aio.live.connect(model=MODEL, config=self.config) as session,
                asyncio.TaskGroup() as tg,
            ):
                self.session = session
                
                # Send persona instructions as the first message if specified
                if self.persona in PERSONAS and PERSONAS[self.persona]:
                    # Send the persona instructions as a system message
                    await session.send(input=f"SYSTEM INSTRUCTION: {PERSONAS[self.persona]}", end_of_turn=True)

                self.audio_in_queue = asyncio.Queue()
                self.out_queue = asyncio.Queue(maxsize=5)

                send_text_task = tg.create_task(self.send_text())
                tg.create_task(self.send_realtime())
                tg.create_task(self.listen_audio())
                if self.video_mode == "camera":
                    tg.create_task(self.get_frames())
                elif self.video_mode == "screen":
                    tg.create_task(self.get_screen())

                tg.create_task(self.receive_audio())
                tg.create_task(self.play_audio())

                await send_text_task
                raise asyncio.CancelledError("User requested exit")

        except asyncio.CancelledError:
            pass
        except ExceptionGroup as EG:
            # Only try to close the audio stream if it exists
            if hasattr(self, 'audio_stream') and self.audio_stream:
                self.audio_stream.close()
            traceback.print_exception(EG)


def list_available_personas():
    print("\nAvailable Personas:")
    for persona_name in PERSONAS.keys():
        print(f"- {persona_name}")


def list_available_voices():
    # These are common Gemini voices, update if needed
    voices = ["Puck", "Ember", "Nova", "Echo", "Tide"]
    print("\nAvailable Voices:")
    for voice in voices:
        print(f"- {voice}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Gemini Voice Bot with Persona Support")
    parser.add_argument(
        "--mode",
        type=str,
        default=DEFAULT_MODE,
        help="pixels to stream from",
        choices=["camera", "screen", "none"],
    )
    parser.add_argument(
        "--persona",
        type=str,
        default=DEFAULT_PERSONA,
        help="persona for the AI to adopt",
        choices=PERSONAS.keys(),
    )
    parser.add_argument(
        "--voice",
        type=str,
        default="Puck",
        help="voice to use (Puck, Ember, Nova, Echo, Tide)",
    )
    parser.add_argument(
        "--list-personas",
        action="store_true",
        help="list available personas and exit",
    )
    parser.add_argument(
        "--list-voices",
        action="store_true",
        help="list available voices and exit",
    )
    
    args = parser.parse_args()
    
    if args.list_personas:
        list_available_personas()
        exit(0)
        
    if args.list_voices:
        list_available_voices()
        exit(0)
    
    main = AudioLoop(video_mode=args.mode, persona=args.persona, voice=args.voice)
    print(f"Starting Gemini Voice Bot with {args.persona} persona using {args.voice} voice...")
    asyncio.run(main.run())