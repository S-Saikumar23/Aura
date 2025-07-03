import os
import pyautogui
import sounddevice as sd
import noisereduce as nr
import numpy as np
import scipy.io.wavfile as wav
import time
import ctypes
import pyttsx3
import webrtcvad
from ctypes import cast, POINTER
from datetime import datetime
from comtypes import CLSCTX_ALL
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
from faster_whisper import WhisperModel
import ollama
import pvporcupine
import struct
import pyaudio
from fuzzywuzzy import fuzz
from tanglish_bert_classifier import classify_intent_bert

# ------------------- SETTINGS -------------------
samplerate = 16000
duration = 5
filename = "audio.wav"
model_name = "phi:latest"  # Ollama model name

# ------------------- INIT ENGINES -------------------
engine = pyttsx3.init()
engine.setProperty("rate", 160)

whisper_model = WhisperModel("medium", device="cuda",compute_type="float16")
vad = webrtcvad.Vad(3)

COMMANDS = {
    "lock my pc": lambda: lock_pc(),
    "take a screenshot": lambda: take_screenshot(),
    "open notepad": lambda: open_app("notepad"),
    "open cmd": lambda: open_app("cmd"),
    "command prompt": lambda: open_app("cmd"),
    "shutdown": lambda: confirm_and_execute("shutdown the system", lambda: open_app("shutdown")),
    "restart": lambda: confirm_and_execute("restart the pc", lambda: open_app("restart")),
    "what time is it now": lambda: tell_time(),
    "mute": lambda: change_volume("mute"),
    "unmute": lambda: change_volume("unmute"),
    "increase volume": lambda: change_volume("up"),
    "decrease volume": lambda: change_volume("down"),
    "tell me your name": lambda: speak("Hi, I'm Aura. It's a pleasure to assist you."),
    "love you": lambda: speak("Thank you! That means a lot to me.")
}

# ------------------- SPEAK FUNCTION -------------------
def speak(text):
    print(f"AURA: {text}")
    engine.say(text)
    engine.runAndWait()

# ------------------- HOTWORD LISTENER -------------------
def listen_for_hotword():
    access_key = "YIMdA49EXkUcutApDFAr/7OkNjOd0/d59kbkVTbnFFSuvLbhYJBDwQ=="
    keyword_path = r"C:\\Users\\Lenovo\\Downloads\\Hey-Aura_en_windows_v3_0_0\\Hey-Aura_en_windows_v3_0_0.ppn"
    porcupine = pvporcupine.create(access_key=access_key, keyword_paths=[keyword_path])

    pa = pyaudio.PyAudio()

    stream = pa.open(
        rate=porcupine.sample_rate,
        channels=1,
        format=pyaudio.paInt16,
        input=True,
        frames_per_buffer=porcupine.frame_length
    )

    print("Listening for 'Hey Aura'...")

    try:
        while True:
            pcm = stream.read(porcupine.frame_length, exception_on_overflow=False)
            pcm_unpacked = struct.unpack_from("h" * porcupine.frame_length, pcm)
            result = porcupine.process(pcm_unpacked)
            if result >= 0:
                print("Hotword 'Hey Aura' detected!")
                speak("Hello! How may I assist you today?")
                break
    finally:
        stream.stop_stream()
        stream.close()
        pa.terminate()
        porcupine.delete()

# ------------------- AUDIO FUNCTIONS -------------------
def is_speech(audio_data):
    audio_bytes = audio_data.tobytes()
    frame_duration = 30
    frame_size = int(samplerate * frame_duration / 1000) * 2
    for i in range(0, len(audio_bytes) - frame_size, frame_size):
        frame = audio_bytes[i:i + frame_size]
        if vad.is_speech(frame, samplerate):
            return True
    return False

def record_audio():
    print("\nListening...")
    recording = sd.rec(int(samplerate * duration), samplerate=samplerate, channels=1, dtype=np.int16)
    sd.wait()
    audio_data = np.squeeze(recording)

    reduced_noise = nr.reduce_noise(y=audio_data, sr=samplerate)
    final_audio = np.int16(reduced_noise)

    if is_speech(final_audio):
        wav.write(filename, samplerate, final_audio)
        print("Speech detected and recorded.")
        return True
    else:
        print("No speech detected.")
        return False

def transcribe_audio():
    print("Transcribing...")
    segments, _ = whisper_model.transcribe(filename)
    full_text = " ".join([segment.text for segment in segments]).lower().strip()
    print(f"You said: {full_text}")
    return full_text

# ------------------- TEXT NORMALIZATION -------------------
def normalize_text(text):
    fillers = [
        "please", "can you", "do you", "could you", "would you", "will you", "hey aura", "aura", "kindly", "i want to"
    ]
    for filler in fillers:
        text = text.replace(filler, "")
    return text.lower().strip()

# ------------------- INTENT CLASSIFICATION -------------------
def classify_intent(text):
    cleaned = normalize_text(text)
    # Rule-based override
    keywords = [
        "shutdown", "restart", "mute", "unmute", "volume", "time", "lock",
        "screenshot", "notepad", "cmd", "command prompt","shutdown"
    ]
    if any(kw in cleaned for kw in keywords):
        return "system_command"

    # Fallback to classifier
    return classify_intent_bert(text)

# ------------------- MATCHING & LLM -------------------
def match_command(text):
    cleaned_text = normalize_text(text)

    # Force exact keyword triggers
    if "command prompt" in cleaned_text or "cmd" in cleaned_text:
        return COMMANDS.get("open cmd")

    best_match = None
    highest_score = 0
    COMMAND_THRESHOLD = 70

    for phrase in COMMANDS:
        score = fuzz.token_set_ratio(cleaned_text, phrase)
        if score >= COMMAND_THRESHOLD and score > highest_score:
            best_match = phrase
            highest_score = score

    if best_match:
        print(f"Fuzzy Matched: {best_match} (score: {highest_score})")
        return COMMANDS[best_match]

    return None

def ask_llm(prompt):
    print("Sending to AI...")

    system_prompt = (
        "You are AURA, an AI assistant who is friendly, interactive, and kind. You respond in a caring and polite tone. "
        "Keep your answers short, helpful, and make the user feel supported and respected."
    )

    response = ollama.chat(
        model=model_name,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ]
    )

    reply = response.get("message", {}).get("content", "").strip()
    
    return reply if reply else "I'm really sorry, I couldn't find an answer for that."

def is_exit_command(text):
    return text in ["exit", "quit", "stop", "close"]

# ------------------- SYSTEM ACTIONS -------------------
def lock_pc():
    speak("Alright, locking your PC now.")
    ctypes.windll.user32.LockWorkStation()

def take_screenshot():
    speak("Sure, taking a screenshot for you.")
    screenshot = pyautogui.screenshot()
    screenshot.save("screenshot.png")
    print("Saved as screenshot.png")

def change_volume(action):
    devices = AudioUtilities.GetSpeakers()
    interface = devices.Activate(IAudioEndpointVolume.iid, CLSCTX_ALL, None)
    volume = cast(interface, POINTER(IAudioEndpointVolume))

    if action == "mute":
        volume.SetMute(1, None)
        speak("Muted the volume.")
    elif action == "unmute":
        volume.SetMute(0, None)
        speak("Unmuted the volume.")
    elif action == "up":
        current = volume.GetMasterVolumeLevelScalar()
        volume.SetMasterVolumeLevelScalar(min(current + 0.1, 1.0), None)
        speak("Volume increased.")
    elif action == "down":
        current = volume.GetMasterVolumeLevelScalar()
        volume.SetMasterVolumeLevelScalar(max(current - 0.1, 0.0), None)
        speak("Volume decreased.")

def tell_time():
    now = datetime.now()
    time_str = now.strftime("The time is %I:%M %p.")
    speak(time_str)

def open_app(command):
    if command == "notepad":
        speak("Opening Notepad for you.")
        os.system("start notepad")
    elif command == "cmd":
        speak("Sure, launching Command Prompt.")
        os.system("start cmd")
    elif command == "shutdown":
        speak("Okay, shutting down your PC.")
        os.system("shutdown /s /t 1")
    elif command == "restart":
        speak("Restarting your PC now.")
        os.system("shutdown /r /t 1")
    else:
        speak("Sorry, I couldn't find a matching app to open.")

def confirm_and_execute(action_name, func):
    speak(f"Are you sure you want to {action_name}? Please say yes to confirm.")
    if record_audio():
        response = transcribe_audio()
        if "yes" in response.lower():
            func()
        else:
            speak("No problem. I've cancelled the request.")

# ------------------- MAIN LOOP -------------------
if __name__ == "__main__":
    speak("AURA is now ready. You can say 'Hey Aura' to begin.")

    while True:
        listen_for_hotword()

        if not record_audio():
            continue

        spoken_text = transcribe_audio()

        if is_exit_command(spoken_text):
            speak("Goodbye! Have a wonderful day ahead.")
            break

        intent = classify_intent(spoken_text)

        if intent == "system_command":
            action = match_command(spoken_text)
            if action:
                action()
            else:
                speak("I couldn't find a matching system command, but I'm here to help with something else.")
        else:
            speak("Let me think about that for a moment...")
            response = ask_llm(spoken_text)
            speak(response)