import streamlit as st
import os
import json
from openai import OpenAI

st.set_page_config(page_title="Realtime Voice AI", page_icon="🎙️", layout="wide")

# Custom CSS
st.markdown("""
<style>
    .status-active { color: #00ff00; font-weight: bold; }
    .status-inactive { color: #ff0000; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

st.title("🎙️ Realtime Voice AI Assistant")
st.markdown("*Speak naturally - interrupt anytime!*")

# API Key check
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    st.error("⚠️ OPENAI_API_KEY not found in environment variables")
    st.stop()

# Session state
if "conversation" not in st.session_state:
    st.session_state.conversation = []
if "is_active" not in st.session_state:
    st.session_state.is_active = False

# Display conversation
chat_container = st.container()
with chat_container:
    for msg in st.session_state.conversation:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

# Control section
col1, col2, col3 = st.columns([1, 1, 2])

with col1:
    if st.button("🎙️ Start", key="start", use_container_width=True):
        st.session_state.is_active = True
        st.rerun()

with col2:
    if st.button("⏹️ Stop", key="stop", use_container_width=True):
        st.session_state.is_active = False
        st.rerun()

with col3:
    if st.session_state.is_active:
        st.markdown('<p class="status-active">🟢 ACTIVE - Listening...</p>', unsafe_allow_html=True)
    else:
        st.markdown('<p class="status-inactive">🔴 INACTIVE</p>', unsafe_allow_html=True)

# JavaScript component for realtime audio
if st.session_state.is_active:
    st.components.v1.html(f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{
                font-family: Arial, sans-serif;
                padding: 20px;
                background: #0e1117;
                color: white;
            }}
            #status {{
                padding: 15px;
                background: #1e1e1e;
                border-radius: 8px;
                margin-bottom: 15px;
            }}
            .log {{
                padding: 5px;
                margin: 3px 0;
                background: #2a2a2a;
                border-radius: 4px;
                font-size: 12px;
            }}
            .user {{ color: #4CAF50; }}
            .assistant {{ color: #2196F3; }}
            .error {{ color: #f44336; }}
        </style>
    </head>
    <body>
        <div id="status">Connecting to OpenAI Realtime API...</div>
        <div id="logs"></div>
        
        <script>
            const API_KEY = '{api_key}';
            const WS_URL = 'wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview-2024-10-01';
            
            let ws = null;
            let audioContext = null;
            let mediaStream = null;
            let processor = null;
            let isPlaying = false;
            let audioQueue = [];
            
            function log(message, className = '') {{
                const logs = document.getElementById('logs');
                const div = document.createElement('div');
                div.className = 'log ' + className;
                div.textContent = new Date().toLocaleTimeString() + ' - ' + message;
                logs.appendChild(div);
                logs.scrollTop = logs.scrollHeight;
            }}
            
            function updateStatus(msg) {{
                document.getElementById('status').textContent = msg;
            }}
            
            async function init() {{
                try {{
                    // Initialize WebSocket
                    ws = new WebSocket(WS_URL, [
                        'realtime',
                        'openai-insecure-api-key.' + API_KEY,
                        'openai-beta.realtime-v1'
                    ]);
                    
                    ws.onopen = async () => {{
                        log('✅ Connected to OpenAI', 'assistant');
                        updateStatus('🟢 Connected - Speak now!');
                        
                        // Configure session
                        ws.send(JSON.stringify({{
                            type: 'session.update',
                            session: {{
                                modalities: ['text', 'audio'],
                                instructions: 'You are a helpful AI assistant. Be conversational, concise, and friendly. Respond naturally to interruptions.',
                                voice: 'alloy',
                                input_audio_format: 'pcm16',
                                output_audio_format: 'pcm16',
                                input_audio_transcription: {{
                                    model: 'whisper-1'
                                }},
                                turn_detection: {{
                                    type: 'server_vad',
                                    threshold: 0.5,
                                    prefix_padding_ms: 300,
                                    silence_duration_ms: 500
                                }}
                            }}
                        }}));
                        
                        // Start audio capture
                        await startAudioCapture();
                    }};
                    
                    ws.onmessage = (event) => {{
                        const data = JSON.parse(event.data);
                        handleServerEvent(data);
                    }};
                    
                    ws.onerror = (error) => {{
                        log('❌ WebSocket error: ' + error.message, 'error');
                    }};
                    
                    ws.onclose = () => {{
                        log('Connection closed', 'error');
                        updateStatus('🔴 Disconnected');
                        cleanup();
                    }};
                    
                }} catch (error) {{
                    log('❌ Initialization error: ' + error.message, 'error');
                }}
            }}
            
            async function startAudioCapture() {{
                try {{
                    mediaStream = await navigator.mediaDevices.getUserMedia({{
                        audio: {{
                            channelCount: 1,
                            sampleRate: 24000,
                            echoCancellation: true,
                            noiseSuppression: true
                        }}
                    }});
                    
                    audioContext = new AudioContext({{ sampleRate: 24000 }});
                    const source = audioContext.createMediaStreamSource(mediaStream);
                    processor = audioContext.createScriptProcessor(4096, 1, 1);
                    
                    processor.onaudioprocess = (e) => {{
                        if (ws && ws.readyState === WebSocket.OPEN) {{
                            const inputData = e.inputBuffer.getChannelData(0);
                            const pcm16 = float32ToPCM16(inputData);
                            const base64Audio = arrayBufferToBase64(pcm16);
                            
                            ws.send(JSON.stringify({{
                                type: 'input_audio_buffer.append',
                                audio: base64Audio
                            }}));
                        }}
                    }};
                    
                    source.connect(processor);
                    processor.connect(audioContext.destination);
                    
                    log('🎤 Microphone active', 'user');
                    
                }} catch (error) {{
                    log('❌ Microphone error: ' + error.message, 'error');
                }}
            }}
            
            function handleServerEvent(event) {{
                switch (event.type) {{
                    case 'conversation.item.input_audio_transcription.completed':
                        log('You: ' + event.transcript, 'user');
                        window.parent.postMessage({{
                            type: 'transcript',
                            role: 'user',
                            content: event.transcript
                        }}, '*');
                        break;
                        
                    case 'response.audio.delta':
                        playAudioChunk(event.delta);
                        break;
                        
                    case 'response.audio_transcript.delta':
                        // Accumulate assistant transcript
                        break;
                        
                    case 'response.audio_transcript.done':
                        log('AI: ' + event.transcript, 'assistant');
                        window.parent.postMessage({{
                            type: 'transcript',
                            role: 'assistant',
                            content: event.transcript
                        }}, '*');
                        break;
                        
                    case 'conversation.item.truncated':
                        log('⚠️ Interruption detected', 'user');
                        stopAudioPlayback();
                        break;
                        
                    case 'error':
                        log('❌ Error: ' + event.error.message, 'error');
                        break;
                }}
            }}
            
            function playAudioChunk(base64Audio) {{
                try {{
                    const pcm16 = base64ToArrayBuffer(base64Audio);
                    const float32 = pcm16ToFloat32(new Int16Array(pcm16));
                    
                    if (!audioContext) return;
                    
                    const audioBuffer = audioContext.createBuffer(1, float32.length, 24000);
                    audioBuffer.getChannelData(0).set(float32);
                    
                    const source = audioContext.createBufferSource();
                    source.buffer = audioBuffer;
                    source.connect(audioContext.destination);
                    source.start();
                    
                }} catch (error) {{
                    console.error('Playback error:', error);
                }}
            }}
            
            function stopAudioPlayback() {{
                if (audioContext) {{
                    audioContext.close().then(() => {{
                        audioContext = new AudioContext({{ sampleRate: 24000 }});
                    }});
                }}
            }}
            
            function cleanup() {{
                if (processor) processor.disconnect();
                if (mediaStream) mediaStream.getTracks().forEach(track => track.stop());
                if (audioContext) audioContext.close();
                if (ws) ws.close();
            }}
            
            // Audio conversion utilities
            function float32ToPCM16(float32Array) {{
                const pcm16 = new Int16Array(float32Array.length);
                for (let i = 0; i < float32Array.length; i++) {{
                    const s = Math.max(-1, Math.min(1, float32Array[i]));
                    pcm16[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
                }}
                return pcm16.buffer;
            }}
            
            function pcm16ToFloat32(pcm16Array) {{
                const float32 = new Float32Array(pcm16Array.length);
                for (let i = 0; i < pcm16Array.length; i++) {{
                    float32[i] = pcm16Array[i] / (pcm16Array[i] < 0 ? 0x8000 : 0x7FFF);
                }}
                return float32;
            }}
            
            function arrayBufferToBase64(buffer) {{
                const bytes = new Uint8Array(buffer);
                let binary = '';
                for (let i = 0; i < bytes.length; i++) {{
                    binary += String.fromCharCode(bytes[i]);
                }}
                return btoa(binary);
            }}
            
            function base64ToArrayBuffer(base64) {{
                const binary = atob(base64);
                const bytes = new Uint8Array(binary.length);
                for (let i = 0; i < binary.length; i++) {{
                    bytes[i] = binary.charCodeAt(i);
                }}
                return bytes.buffer;
            }}
            
            // Start on load
            window.addEventListener('load', init);
            window.addEventListener('beforeunload', cleanup);
        </script>
    </body>
    </html>
    """, height=400)
    
    # Listen for messages from iframe
    st.markdown("""
    <script>
        window.addEventListener('message', function(event) {
            if (event.data.type === 'transcript') {
                // Send to Streamlit
                window.parent.postMessage({
                    isStreamlitMessage: true,
                    type: 'transcript',
                    ...event.data
                }, '*');
            }
        });
    </script>
    """, unsafe_allow_html=True)

if st.button("Clear Conversation"):
    st.session_state.conversation = []
    st.rerun()