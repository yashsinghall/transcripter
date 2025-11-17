import streamlit as st
import pandas as pd
import requests
import json
from io import BytesIO
import base64
import os
import time

st.set_page_config(page_title="Call Recording Transcriber", layout="wide")

st.title("🎙️ Call Recording Transcriber")
st.markdown("Transcribe call recordings with speaker identification using Gemini API")

def format_transcript_gemini(gemini_response):
    """Extract and format transcript from Gemini response"""
    try:
        if not gemini_response or len(gemini_response) == 0:
            return "No transcript generated"
        
        # Gemini returns response in parts
        content_parts = gemini_response[0].get("content", {}).get("parts", [])
        if not content_parts:
            return "No transcript generated"
        
        text_content = content_parts[0].get("text", "")
        if not text_content:
            return "No transcript generated"
        
        return text_content
    
    except Exception as e:
        return f"Error parsing transcript: {str(e)}"

# Sidebar configuration
st.sidebar.header("Configuration")

# API Key input
api_key = st.sidebar.text_input(
    "Gemini API Key",
    type="password",
    help="Your Google Gemini API key"
)

# Language selection
st.sidebar.subheader("Language Settings")
language_mode = st.sidebar.radio(
    "Choose language mode:",
    ["English (India)", "Hindi", "Mixed (English + Hindi)"],
    help="Select the language(s) in your call recordings"
)

if language_mode == "English (India)":
    language_prompt = "English (Indian accent)"
    st.sidebar.info("ℹ️ Processing in English (Indian English)")
    
elif language_mode == "Hindi":
    language_prompt = "Hindi (Devanagari script)"
    st.sidebar.info("ℹ️ Processing in Hindi (Devanagari script)")
    
else:  # Mixed (English + Hindi)
    language_prompt = "Mixed English and Hindi (code-switching)"
    st.sidebar.info("⚠️ Mixed mode will detect both English and Hindi automatically")

# Transcription settings
col1, col2 = st.sidebar.columns(2)
with col1:
    min_speakers = st.sidebar.number_input("Min Speakers", value=2, min_value=1, max_value=6)
with col2:
    max_speakers = st.sidebar.number_input("Max Speakers", value=2, min_value=1, max_value=6)

st.sidebar.info("✨ Using Google Gemini API for superior speaker diarization")

# Main content
tab1, tab2, tab3 = st.tabs(["Upload & Process", "Instructions", "Debug"])

with tab1:
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📁 Upload Excel File")
        uploaded_file = st.file_uploader("Select Excel file (.xlsx)", type=["xlsx"])
        
        if uploaded_file:
            st.info(f"✓ File loaded: {uploaded_file.name}")
            try:
                df = pd.read_excel(uploaded_file)
                st.write(f"Rows: {len(df)} | Columns: {len(df.columns)}")
                
                # Show required columns
                if "recording_url" in df.columns:
                    st.success("✓ Found 'recording_url' column")
                else:
                    st.error("✗ Missing 'recording_url' column")
                
                if "mobile_number" in df.columns:
                    st.success("✓ Found 'mobile_number' column")
                else:
                    st.warning("⚠ Missing 'mobile_number' column (optional)")
                    
            except Exception as e:
                st.error(f"Error reading file: {str(e)}")
    
    with col2:
        st.subheader("⚙️ Settings")
        st.metric("Min Speakers", int(min_speakers))
        st.metric("Max Speakers", int(max_speakers))
        st.write(f"**Language:** {language_mode}")

# Process button
if st.button("🚀 Process Recordings", use_container_width=True, type="primary"):
    if not api_key:
        st.error("Please enter your Gemini API key in the sidebar")
    elif not uploaded_file:
        st.error("Please upload an Excel file")
    else:
        try:
            df = pd.read_excel(uploaded_file)
            
            if "recording_url" not in df.columns:
                st.error("Excel file must contain 'recording_url' column")
            else:
                # Process recordings
                progress_bar = st.progress(0)
                status_container = st.empty()
                results_data = []
                
                # Add transcript column if not exists
                if "transcript" not in df.columns:
                    df["transcript"] = ""
                
                for idx, row in df.iterrows():
                    current = idx + 1
                    total = len(df)
                    progress = current / total
                    progress_bar.progress(progress)
                    
                    mobile = row.get("mobile_number", "Unknown")
                    status_container.info(f"Processing {current} of {total}: {mobile}... (using Gemini API)")
                    
                    try:
                        # Download audio
                        audio_url = row["recording_url"]
                        audio_response = requests.get(audio_url, timeout=30)
                        audio_response.raise_for_status()
                        
                        # Convert to base64
                        audio_base64 = base64.b64encode(audio_response.content).decode()
                        
                        # Determine MIME type based on file extension
                        mime_type = "audio/mpeg"  # Default to MP3
                        if audio_url.lower().endswith(".wav"):
                            mime_type = "audio/wav"
                        elif audio_url.lower().endswith(".ogg"):
                            mime_type = "audio/ogg"
                        elif audio_url.lower().endswith(".flac"):
                            mime_type = "audio/flac"
                        elif audio_url.lower().endswith(".m4a"):
                            mime_type = "audio/mp4"
                        
                        # Build prompt for Gemini
                        prompt = f"""Transcribe this call recording in {language_prompt}.

IMPORTANT REQUIREMENTS:
1. Identify and label different speakers (Speaker 1, Speaker 2, etc.)
2. Include timestamps in milliseconds for each speaker's segment [startMs to endMs]
3. Format: Speaker X - "text here" [startTime ms to endTime ms]
4. Ensure you capture at least {int(min_speakers)} speakers if present
5. Check for up to {int(max_speakers)} different speakers
6. Use exact language of the audio
7. Include punctuation

Output format example:
Speaker 1 - "Hello, how can I help?" [0ms to 2500ms]
Speaker 2 - "I need help with my account" [2600ms to 5000ms]
Speaker 1 - "Sure, let me look that up" [5100ms to 8000ms]

Now transcribe the audio:"""
                        
                        # Call Gemini API with audio
                        api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
                        
                        headers = {
                            "Content-Type": "application/json",
                        }
                        
                        payload = {
                            "contents": [
                                {
                                    "parts": [
                                        {
                                            "text": prompt
                                        },
                                        {
                                            "inline_data": {
                                                "mime_type": mime_type,
                                                "data": audio_base64
                                            }
                                        }
                                    ]
                                }
                            ],
                            "generationConfig": {
                                "temperature": 0.3,
                                "topK": 40,
                                "topP": 0.95,
                                "maxOutputTokens": 4096,
                            }
                        }
                        
                        response = requests.post(
                            api_url,
                            json=payload,
                            headers=headers,
                            timeout=120
                        )
                        
                        if response.status_code != 200:
                            error_data = response.json()
                            error_msg = error_data.get("error", {}).get("message", "Unknown error")
                            df.at[idx, "transcript"] = f"ERROR: {error_msg}"
                            results_data.append({
                                "mobile": mobile,
                                "status": "❌ Failed",
                                "details": error_msg[:50]
                            })
                        else:
                            result = response.json()
                            candidates = result.get("candidates", [])
                            
                            if not candidates:
                                df.at[idx, "transcript"] = "ERROR: No response from Gemini"
                                results_data.append({
                                    "mobile": mobile,
                                    "status": "❌ Failed",
                                    "details": "No response"
                                })
                            else:
                                transcript = format_transcript_gemini(candidates)
                                df.at[idx, "transcript"] = transcript
                                
                                if transcript.startswith("ERROR") or transcript == "No transcript generated":
                                    results_data.append({
                                        "mobile": mobile,
                                        "status": "⚠️ No data",
                                        "details": transcript[:50]
                                    })
                                else:
                                    lines = len(transcript.split('\n'))
                                    results_data.append({
                                        "mobile": mobile,
                                        "status": "✅ Success",
                                        "details": f"{lines} segments"
                                    })
                    
                    except requests.exceptions.Timeout:
                        df.at[idx, "transcript"] = "ERROR: Request timeout"
                        results_data.append({
                            "mobile": mobile,
                            "status": "❌ Failed",
                            "details": "Timeout"
                        })
                    except Exception as e:
                        df.at[idx, "transcript"] = f"ERROR: {str(e)}"
                        results_data.append({
                            "mobile": mobile,
                            "status": "❌ Failed",
                            "details": str(e)[:50]
                        })
                
                progress_bar.progress(1.0)
                status_container.success("✅ All recordings processed!")
                
                # Show results table
                st.subheader("📊 Processing Results")
                results_df = pd.DataFrame(results_data)
                st.dataframe(results_df, use_container_width=True, hide_index=True)
                
                # Download button
                st.subheader("📥 Download Results")
                output = BytesIO()
                df.to_excel(output, index=False, sheet_name="Transcripts")
                output.seek(0)
                
                st.download_button(
                    label="Download Excel with Transcripts",
                    data=output,
                    file_name=f"call_transcripts_{pd.Timestamp.now().strftime('%Y-%m-%d')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
                
                # Show sample transcript
                st.subheader("📝 Sample Transcript")
                sample_idx = None
                for idx, row in df.iterrows():
                    if isinstance(row["transcript"], str) and not row["transcript"].startswith("ERROR") and row["transcript"] != "No transcript generated":
                        sample_idx = idx
                        break
                
                if sample_idx is not None:
                    st.text_area(
                        "Sample from first successful transcription:",
                        value=df.at[sample_idx, "transcript"],
                        height=200,
                        disabled=True
                    )
        
        except Exception as e:
            st.error(f"Error: {str(e)}")

with tab2:
    st.subheader("📋 How to Use")
    
    st.markdown("""
    ### Step 1: Get Gemini API Key
    1. Go to [Google AI Studio](https://aistudio.google.com/app/apikeys)
    2. Click "Create API Key" 
    3. Copy the API key and paste in the sidebar
    
    ### Step 2: Prepare Excel File
    - Your Excel file must have a **`recording_url`** column
    - Optional: Add **`mobile_number`** column for reference
    - Other columns will be preserved in output
    
    ### Step 3: Select Language Mode
    
    **Language Modes:**
    - **English (India)**: For English-only call recordings
    - **Hindi**: For Hindi-only call recordings (Devanagari script)
    - **Mixed (English + Hindi)**: For bilingual calls with code-switching
    
    - **Min/Max Speakers**: Set to 2 for typical call recordings
    
    ### Step 4: Process & Download
    - Click **Process Recordings** button
    - Gemini API will analyze audio with superior speaker diarization
    - Processing takes 1-2 minutes per recording
    - Download the updated Excel file with transcripts
    
    ### Output Format
    Each transcript line contains:
    ```
    Speaker 1 - "text here" [startTime ms to endTime ms]
    Speaker 2 - "response" [startTime ms to endTime ms]
    ```
    
    ### Supported Audio Formats
    - MP3, WAV, OGG, FLAC, M4A
    - Must be accessible via URL
    - Audio should be clear call recordings
    
    ### Language Support
    - **English (India)**: Indian English accents
    - **Hindi**: Devanagari script Hindi
    - **Mixed**: Bilingual conversations with code-switching
    
    ### Why Gemini?
    - **Superior Speaker Detection**: Gemini's multimodal AI is excellent at identifying different speakers
    - **Natural Language Understanding**: Better context awareness
    - **Flexible Formatting**: Can follow specific output patterns
    - **Multilingual**: Excellent with Hindi and English mixing
    - **Fast Processing**: 1-2 minutes per recording vs 5-10 minutes with Google Speech
    
    ### Troubleshooting
    
    **Still only seeing Speaker 1**:
    - Ensure audio has clear voice differences between speakers
    - Check audio quality - very compressed audio may lose speaker distinction
    - Try increasing Max Speakers to 3 or 4
    - Audio needs at least 500ms of speech per speaker for detection
    
    **"No transcript generated"**: 
    - Audio might be too noisy or corrupted
    - Verify URL is directly accessible
    - Try with a shorter test audio first
    
    **API Errors**:
    - Verify your Gemini API key is valid
    - Check that you have API quota remaining
    - Ensure audio file is less than 20MB
    
    ### Tips
    - Start with 1-2 test recordings first
    - Ensure audio quality is good (clear voices)
    - For bilingual calls, use "Mixed" mode
    - Gemini works best with natural conversational audio
    - Keep API key secure (never share it)
    """)

with tab3:
    st.subheader("🔍 Debug Information")
    
    st.write("**Using Google Gemini API**")
    st.write("- Model: `gemini-1.5-flash` (faster) or `gemini-1.5-pro` (more accurate)")
    st.write("- Supports multimodal: Audio + Text prompts")
    st.write("- Excellent speaker diarization capabilities")
    st.write("- Processing: 1-2 minutes per recording")
    
    if st.button("Test Gemini Connection"):
        if not api_key:
            st.error("Please enter your Gemini API key in sidebar first")
        else:
            try:
                # Test with a simple text request
                api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
                
                payload = {
                    "contents": [
                        {
                            "parts": [
                                {
                                    "text": "Say 'Gemini API connection successful' in exactly one line."
                                }
                            ]
                        }
                    ]
                }
                
                response = requests.post(
                    api_url,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                    timeout=10
                )
                
                if response.status_code == 200:
                    st.success("✅ Gemini API connection successful!")
                    result = response.json()
                    candidates = result.get("candidates", [])
                    if candidates:
                        text = candidates[0]["content"]["parts"][0]["text"]
                        st.write(f"Response: {text}")
                else:
                    error_data = response.json()
                    st.error(f"API Error: {response.status_code}")
                    st.json(error_data)
            except Exception as e:
                st.error(f"Connection test failed: {str(e)}")
