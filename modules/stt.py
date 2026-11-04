# Core: MK-Agentic-System · Powered by FENIX Engine · (c) 2026 Mustafa Koç · GPL-3.0-only (LICENSE, NOTICE.md)
"""
Konuşmayı Yazıya Çevirme (STT)
------------------------------
1) Kayıt kontrolü: kayıt boş mu, çok kısa mı, mikrofon sessiz mi? (sebep kullanıcıya söylenir)
2) Groq Whisper (anahtar varsa): Türkçede çok daha isabetli ve hızlı
3) Yedek: Google ücretsiz tanıma (speech_recognition)

transcribe() her zaman (metin, sebep) döner; metin None ise sebep kullanıcıya gösterilir.
"""
import io
import wave

import numpy as np

GROQ_URL = "https://api.groq.com/openai/v1/audio/transcriptions"


def analyze(wav_bytes):
    """Kaydın süresini ve ses seviyesini ölçer: (saniye, tepe 0..1, rms 0..1)"""
    with wave.open(io.BytesIO(wav_bytes)) as wf:
        rate, n = wf.getframerate(), wf.getnframes()
        data = np.frombuffer(wf.readframes(n), dtype=np.int16).astype(np.float32) / 32768.0
    if data.size == 0:
        return 0.0, 0.0, 0.0
    return n / float(rate or 16000), float(np.abs(data).max()), float(np.sqrt(np.mean(data ** 2)))


def _groq(wav_bytes, api_key, model, prompt=""):
    import requests
    files = {"file": ("ses.wav", wav_bytes, "audio/wav")}
    from . import i18n
    data = {"model": model, "language": i18n.stt_whisper(), "response_format": "json", "temperature": "0"}
    if prompt:
        data["prompt"] = prompt
    r = requests.post(GROQ_URL, headers={"Authorization": f"Bearer {api_key}"}, files=files, data=data, timeout=60)
    if r.status_code >= 400:
        raise RuntimeError(f"Groq STT {r.status_code}: {r.text[:200]}")
    return (r.json().get("text") or "").strip()


def _google(wav_bytes):
    import speech_recognition as sr
    from . import i18n
    r = sr.Recognizer()
    with sr.AudioFile(io.BytesIO(wav_bytes)) as src:
        audio = r.record(src)
    try:
        return r.recognize_google(audio, language=i18n.stt_google()), None
    except sr.UnknownValueError:
        return None, "anlaşılamadı"
    except sr.RequestError as e:
        return None, f"Google tanıma servisine ulaşılamadı ({str(e)[:80]})"


# Whisper sessiz/gürültülü kayıtta bazen bu kalıpları "uydurur"; bunları boş sonuç say
_HALLUCINATIONS = ("altyazı", "abone ol", "izlediğiniz için teşekkür", "m.k.", "www.")


def transcribe(wav_bytes, groq_key="", model="whisper-large-v3-turbo", device_name="", min_seconds=0.4,
               silence_peak=0.02, on_error=None):
    """(metin, sebep) döner. on_error(where, detail): hata ayrıntısını kaydetmek için."""
    if not wav_bytes:
        return None, "Ses kaydı alınamadı (mikrofon hiç veri göndermedi)."
    try:
        secs, peak, _rms = analyze(wav_bytes)
    except Exception:
        secs, peak = 1.0, 1.0
    if secs < min_seconds:
        return None, "Kayıt çok kısa; butona basıp konuştuktan sonra bırak."
    if peak < silence_peak:
        dev = f" ({device_name})" if device_name else ""
        return None, (f"Mikrofondan ses gelmiyor{dev}. Windows ses ayarlarında doğru mikrofonun seçili ve "
                      "sesinin açık olduğundan emin ol; gerekirse config.yaml'da audio.input_device ile seç.")

    reasons = []
    if groq_key:
        for m in dict.fromkeys([model, "whisper-large-v3-turbo", "whisper-large-v3"]):
            try:
                text = _groq(wav_bytes, groq_key, m)
                if text and not any(h in text.lower() for h in _HALLUCINATIONS):
                    return text, None
                if text:
                    reasons.append("Whisper sessizlik algıladı")
                    break
                reasons.append("Whisper boş döndü")
                break
            except Exception as e:
                reasons.append(str(e)[:160])
                if on_error:
                    on_error("ses tanıma (Groq)", str(e))
                if "404" not in str(e) and "model" not in str(e).lower():
                    break

    text, why = _google(wav_bytes)
    if text:
        return text, None
    if why and why != "anlaşılamadı" and on_error:
        on_error("ses tanıma (Google)", why)
    if why == "anlaşılamadı":
        return None, "Söylediğin anlaşılamadı, biraz daha yakından ve net konuşup tekrar dene."
    return None, why or ("Ses tanınamadı: " + "; ".join(reasons))
