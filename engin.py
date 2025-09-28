from TTS.api import TTS

# XTTS modelini yükle (multilingual = çok dilli, TR destekli)
tts = TTS(model_name="tts_models/multilingual/multi-dataset/xtts_v2")

# Basit test
tts.tts_to_file(
    text="Merhaba, bu Coqui TTS ile oluşturuldu.",
    file_path="deneme.wav",
    speaker_wav=None,   # Eğer ses klonlamak istersen buraya bir örnek wav dosyası verebilirsin
    language="tr"
)
