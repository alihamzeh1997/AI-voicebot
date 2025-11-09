import streamlit as st
from openai import OpenAI
import base64
import json
import os

st.set_page_config(page_title="Voice Chat Bot", page_icon="🎙️")
st.title("🎙️ Voice Chat Bot")

# Initialize OpenAI
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

if "messages" not in st.session_state:
    st.session_state.messages = []

# Display chat
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])
        if "audio" in msg:
            st.audio(msg["audio"], format="audio/mp3")

# Audio input
audio_file = st.audio_input("🎤 Record your message")

if audio_file:
    # Transcribe
    audio_file.seek(0)
    transcript = client.audio.transcriptions.create(
        model="whisper-1", 
        file=audio_file
    )
    
    user_text = transcript.text
    st.session_state.messages.append({"role": "user", "content": user_text})
    
    # Get response
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": m["role"], "content": m["content"]} 
                  for m in st.session_state.messages]
    )
    
    assistant_text = response.choices[0].message.content
    
    # Text to speech
    speech = client.audio.speech.create(
        model="tts-1",
        voice="alloy",
        input=assistant_text
    )
    
    audio_bytes = speech.content
    
    st.session_state.messages.append({
        "role": "assistant", 
        "content": assistant_text,
        "audio": audio_bytes
    })
    
    st.rerun()

if st.button("Clear Chat"):
    st.session_state.messages = []
    st.rerun()