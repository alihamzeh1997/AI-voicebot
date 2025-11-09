import streamlit as st
import asyncio
import base64
import json
import pyaudio
import os
from websockets.sync.client import connect

# Page config
st.set_page_config(page_title="Realtime AI Voice Chat", page_icon="🎙️")
st.title("🎙️ Realtime AI Voice Chat")

# Audio settings
CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 24000

# Initialize session state
if "is_running" not in st.session_state:
    st.session_state.is_running = False
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display chat messages
chat_container = st.container()
with chat_container:
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

# Status indicator
status = st.empty()

# Control buttons
col1, col2 = st.columns(2)
start_btn = col1.button("🎙️ Start Conversation", disabled=st.session_state.is_running)
stop_btn = col2.button("⏹️ Stop", disabled=not st.session_state.is_running)


def run_realtime_chat():
    """Run the realtime voice chat"""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        st.error("OPENAI_API_KEY not found in environment")
        return

    url = "wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview-2024-10-01"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "OpenAI-Beta": "realtime=v1",
    }

    # Initialize PyAudio
    p = pyaudio.PyAudio()
    input_stream = p.open(
        format=FORMAT, channels=CHANNELS, rate=RATE, input=True, frames_per_buffer=CHUNK
    )
    output_stream = p.open(
        format=FORMAT,
        channels=CHANNELS,
        rate=RATE,
        output=True,
        frames_per_buffer=CHUNK,
    )

    try:
        with connect(url, additional_headers=headers) as ws:
            status.success("🟢 Connected! Start speaking...")

            # Send session configuration
            session_update = {
                "type": "session.update",
                "session": {
                    "modalities": ["text", "audio"],
                    "instructions": "You are a helpful AI assistant. Be conversational and friendly.",
                    "voice": "alloy",
                    "input_audio_format": "pcm16",
                    "output_audio_format": "pcm16",
                    "turn_detection": {"type": "server_vad"},
                },
            }
            ws.send(json.dumps(session_update))

            def send_audio():
                """Send audio from microphone to API"""
                while st.session_state.is_running:
                    try:
                        audio_data = input_stream.read(CHUNK, exception_on_overflow=False)
                        audio_b64 = base64.b64encode(audio_data).decode()
                        event = {
                            "type": "input_audio_buffer.append",
                            "audio": audio_b64,
                        }
                        ws.send(json.dumps(event))
                    except Exception as e:
                        print(f"Send error: {e}")
                        break

            def receive_audio():
                """Receive and play audio responses"""
                transcript_buffer = ""
                
                while st.session_state.is_running:
                    try:
                        message = ws.recv(timeout=0.1)
                        event = json.loads(message)
                        
                        # Handle audio responses
                        if event["type"] == "response.audio.delta":
                            audio_b64 = event["delta"]
                            audio_data = base64.b64decode(audio_b64)
                            output_stream.write(audio_data)
                        
                        # Handle transcripts
                        elif event["type"] == "conversation.item.input_audio_transcription.completed":
                            user_text = event["transcript"]
                            st.session_state.messages.append(
                                {"role": "user", "content": user_text}
                            )
                        
                        elif event["type"] == "response.text.delta":
                            transcript_buffer += event["delta"]
                        
                        elif event["type"] == "response.text.done":
                            if transcript_buffer:
                                st.session_state.messages.append(
                                    {"role": "assistant", "content": transcript_buffer}
                                )
                                transcript_buffer = ""
                        
                        elif event["type"] == "response.audio_transcript.delta":
                            transcript_buffer += event["delta"]
                        
                        elif event["type"] == "response.audio_transcript.done":
                            if transcript_buffer:
                                st.session_state.messages.append(
                                    {"role": "assistant", "content": transcript_buffer}
                                )
                                transcript_buffer = ""
                                
                    except TimeoutError:
                        continue
                    except Exception as e:
                        print(f"Receive error: {e}")
                        break

            # Run both send and receive
            import threading

            send_thread = threading.Thread(target=send_audio, daemon=True)
            receive_thread = threading.Thread(target=receive_audio, daemon=True)

            send_thread.start()
            receive_thread.start()

            # Wait until stopped
            while st.session_state.is_running:
                asyncio.sleep(0.1)

            send_thread.join(timeout=1)
            receive_thread.join(timeout=1)

    except Exception as e:
        st.error(f"Connection error: {e}")
    finally:
        input_stream.stop_stream()
        input_stream.close()
        output_stream.stop_stream()
        output_stream.close()
        p.terminate()
        status.info("⚫ Disconnected")


if start_btn:
    st.session_state.is_running = True
    st.rerun()

if stop_btn:
    st.session_state.is_running = False
    st.rerun()

# Run the chat if active
if st.session_state.is_running:
    run_realtime_chat()

# Clear chat
if st.button("Clear Chat History"):
    st.session_state.messages = []
    st.rerun()