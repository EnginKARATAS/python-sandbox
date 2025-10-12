from bark import SAMPLE_RATE, generate_audio, preload_models
from scipy.io.wavfile import write as write_wav
import time

print("Starting Bark TTS...")
print("Note: This will take several minutes on CPU. Please be patient!")

# download and load all models
print("Loading models... (this may take a while on first run)")
start_time = time.time()
preload_models()
print(f"Models loaded in {time.time() - start_time:.2f} seconds")

# generate audio from text
text_prompt = """
     Hello, my name is Suno. And, uh — and I like pizza. [laughs] 
     But I also have other interests such as playing tic tac toe.
"""

print("Generating audio... (this will take several minutes on CPU)")
start_time = time.time()
audio_array = generate_audio(text_prompt)
print(f"Audio generated in {time.time() - start_time:.2f} seconds")

# save audio to disk
output_file = "bark_generation.wav"
write_wav(output_file, SAMPLE_RATE, audio_array)
print(f"Audio saved to: {output_file}")
print("Done!")