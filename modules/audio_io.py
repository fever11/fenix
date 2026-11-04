# Core: MK-Agentic-System · Powered by FENIX Engine · (c) 2026 Mustafa Koç · GPL-3.0-only (LICENSE, NOTICE.md)
"""Kulaklar ve Ses: Push-to-Talk kayıt + kuyruklu, durdurulabilir, yalnızca Türkçe (erkek) TTS."""
import io
import os
import re
import queue
import wave
import asyncio
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import sounddevice as sd
import keyboard


class _Lazy:
    """Ağır ses kütüphaneleri (edge_tts ~0,3 sn, pygame ~0,5 sn) açılışı yavaşlatmasın: ilk kullanımda yüklenir."""
    def __init__(self, name):
        self._name, self._mod = name, None

    def __getattr__(self, attr):
        if self._mod is None:
            import importlib
            if self._name == "pygame":
                os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
            self._mod = importlib.import_module(self._name)
        return getattr(self._mod, attr)


edge_tts = _Lazy("edge_tts")
pygame = _Lazy("pygame")

def _fire(cb):
    if not cb:
        return
    threading.Thread(target=lambda: _safe(cb), daemon=True).start()


def _safe(cb):
    try:
        cb()
    except Exception:
        pass


class MicError(Exception):
    pass


def _refresh_portaudio():
    """PortAudio cihaz listesini uygulama açılırken bir kez okur; sonradan takılan mikrofonu görmez.
    Açık akış yokken yeniden başlatıp listeyi tazeler."""
    try:
        sd._terminate()
        sd._initialize()
    except Exception as e:
        print(f"[MİKROFON] cihaz listesi yenilenemedi: {e}")


def list_input_devices():
    """[(index, ad, varsayılan_mı)] — sadece giriş (mikrofon) cihazları."""
    try:
        default_in = sd.default.device[0] if isinstance(sd.default.device, (list, tuple)) else sd.default.device
    except Exception:
        default_in = None
    out, seen = [], set()
    try:
        apis = sd.query_hostapis()
        for idx, d in enumerate(sd.query_devices()):
            if d.get("max_input_channels", 0) < 1:
                continue
            api = apis[d["hostapi"]]["name"] if apis else ""
            if "WDM-KS" in api:                     # Windows çekirdek akışı: genelde açılamaz, listeyi kirletir
                continue
            key = (d["name"], api)
            if key in seen:
                continue
            seen.add(key)
            out.append((idx, f"{d['name']}  [{api}]", idx == default_in))
    except Exception as e:
        print(f"[MİKROFON] cihazlar okunamadı: {e}")
    return out


class PushToTalkRecorder:
    def __init__(self, key="f9", sample_rate=16000, device=None):
        self.key = key
        self.sample_rate = sample_rate
        self.device_pref = device          # None/"" = Windows varsayılanı; sayı = cihaz no; metin = ad parçası
        self.rate_used = sample_rate
        self.device_name = "varsayılan"
        self.level = 0.0                   # anlık ses seviyesi 0..1 (arayüzdeki gösterge için)
        self.peak = 0.0                    # kayıt boyunca en yüksek seviye
        self._buffer = []
        self._recording = False
        self._stream = None

    # ---------------- cihaz ----------------
    def _resolve_device(self):
        pref = self.device_pref
        if pref in (None, "", "default", "varsayılan"):
            return None
        if isinstance(pref, int) or (isinstance(pref, str) and pref.strip().isdigit()):
            return int(pref)
        for idx, name, _ in list_input_devices():
            if str(pref).lower() in name.lower():
                return idx
        print(f"[MİKROFON] '{pref}' adlı mikrofon bulunamadı, varsayılan kullanılıyor")
        return None

    def _open(self):
        _refresh_portaudio()
        dev = self._resolve_device()
        try:
            info = sd.query_devices(dev, "input")
            self.device_name = info.get("name", "varsayılan")
        except Exception as e:
            raise MicError(f"Mikrofon bulunamadı ya da kullanılamıyor: {e}")
        last = None
        # Önce 16 kHz; cihaz desteklemiyorsa kendi varsayılan hızıyla kaydet (tanıma her hızı kabul eder)
        for rate in (self.sample_rate, int(info.get("default_samplerate") or 44100), 48000, 44100):
            try:
                stream = sd.InputStream(device=dev, samplerate=rate, channels=1, dtype="int16",
                                        callback=self._callback)
                stream.start()
                self.rate_used = rate
                return stream
            except Exception as e:
                last = e
        raise MicError(f"Mikrofon açılamadı ({self.device_name}): {last}")

    def _callback(self, indata, frames, t, status):
        if self._recording:
            self._buffer.append(indata.copy())
            try:
                lv = float(np.abs(indata).max()) / 32768.0
                self.level = lv
                self.peak = max(self.peak, lv)
            except Exception:
                pass

    def _start(self):
        self._buffer = []
        self.level = self.peak = 0.0
        self._recording = True
        try:
            self._stream = self._open()
        except Exception:
            self._recording = False
            raise

    def _finish(self):
        self._recording = False
        try:
            if self._stream:
                self._stream.stop()
                self._stream.close()
        except Exception:
            pass
        self._stream = None
        self.level = 0.0
        if not self._buffer:
            return None
        audio = np.concatenate(self._buffer, axis=0)
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(self.rate_used)
            wf.writeframes(audio.tobytes())
        return buf.getvalue()

    # ---------------- F9 (tuş basılı tutulurken) ----------------
    def record(self, on_start=None, on_stop=None):
        keyboard.wait(self.key)
        self._start()
        _fire(on_start)
        while keyboard.is_pressed(self.key):
            sd.sleep(50)
        wav = self._finish()
        _fire(on_stop)
        return wav

    # ---------------- arayüz butonu ----------------
    def record_until_released_async(self, on_start=None, on_stop=None, on_done=None):
        """UI mikrofon butonu: hemen kayda başlar, stop_async() çağrılınca biter.
        Mikrofon açılamazsa MicError fırlatır."""
        self._start()
        _fire(on_start)

    def stop_async(self, on_stop=None):
        wav = self._finish()
        _fire(on_stop)
        return wav


DEFAULT_VOICE = "tr-TR-AhmetNeural"   # yalnızca Türkçe, erkek ses

_URL_RE = re.compile(r"https?://\S+")
_CODE_RE = re.compile(r"```.*?```", re.DOTALL)


_SOURCES_HEAD_RE = re.compile(
    r"^\s*(?:#{1,6}\s*)?[*_]*\s*(?:kaynak|kaynaklar|kaynakça|incelenen|inceleme yapılan|incelenen kaynaklar|"
    r"okunan kaynaklar|taranan sayfalar|referanslar|sources|references)\b", re.IGNORECASE)
_DOMAIN_RE = re.compile(r"\b(?:www\.)?[\w\-]+\.(?:com|net|org|io|dev|gov|edu|co|ai|app|tr)(?:\.tr)?(?:/\S*)?",
                        re.IGNORECASE)
_CITE_RE = re.compile(r"\[\d+(?:\s*[,\-–]\s*\d+)*\]")


def _drop_sources(text):
    """'Kaynaklar' gibi başlıklı bölümleri bir sonraki başlığa kadar atar (kaynakça yazıda kalır, okunmaz)."""
    out, skipping = [], False
    for line in text.split("\n"):
        if _SOURCES_HEAD_RE.match(line):
            skipping = True
            continue
        if skipping and re.match(r"^\s*#{1,6}\s+", line):
            skipping = False
        if not skipping:
            out.append(line)
    return "\n".join(out)


def clean_for_speech(text):
    """Sesli okunmayacak şeyleri temizler: kod blokları, kaynak bölümleri, linkler/alan adları,
    [1] gibi atıf numaraları, markdown işaretleri."""
    text = _CODE_RE.sub(" kod bloğu ekranda. ", text or "")
    text = _drop_sources(text)
    text = _URL_RE.sub(" ", text)
    text = _DOMAIN_RE.sub(" ", text)
    text = _CITE_RE.sub("", text)
    text = re.sub(r"^\s*-{3,}\s*$", " ", text, flags=re.MULTILINE)
    text = re.sub(r"[*_`#>|~]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _chunks(text, limit=220):
    """Uzun metni cümle sınırlarından parçalara böler (ilk parça kısa: ses hemen başlasın)."""
    sentences = re.split(r"(?<=[.!?…])\s+|\n+", text)
    out, cur = [], ""
    for sent in sentences:
        sent = sent.strip()
        if not sent:
            continue
        lim = 90 if not out else limit
        if cur and len(cur) + len(sent) + 1 > lim:
            out.append(cur)
            cur = sent
        else:
            cur = f"{cur} {sent}".strip()
        while len(cur) > limit * 1.5:           # çok uzun cümle
            cut = cur.rfind(" ", 0, limit)
            cut = cut if cut > 0 else limit
            out.append(cur[:cut])
            cur = cur[cut:].strip()
    if cur:
        out.append(cur)
    return out


class TTSPlayer:
    """Tek sıralı ses çalıcı.
    - speak() beklemez, kuyruğa ekler (arayüz/araç çağrısını bloklamaz).
    - Uzun cevaplar parçalanır; bir parça çalarken sonraki sentezlenir (gecikme olmaz).
    - stop() anında susturur ve kuyruğu boşaltır.
    - Her parça benzersiz dosyaya yazılır (eski sürümdeki tek dosya çakışması yok)."""

    def __init__(self):
        self._q = queue.Queue()
        self._gen = 0
        self._speaking = False
        self._mixer_ok = False
        self._counter = 0
        self._lock = threading.Lock()
        threading.Thread(target=self._worker, daemon=True).start()

    # --- dış API ---
    def speak(self, text, voice=DEFAULT_VOICE):
        text = clean_for_speech(text)
        if text:
            self._q.put((self._gen, text, voice))
            self._speaking = True

    def stop(self):
        with self._lock:
            self._gen += 1
        try:
            while True:
                self._q.get_nowait()
        except queue.Empty:
            pass
        try:
            if self._mixer_ok:
                pygame.mixer.music.stop()
        except Exception:
            pass
        self._speaking = False

    def is_speaking(self):
        return self._speaking or not self._q.empty()

    # --- iç ---
    def _ensure_mixer(self):
        if not self._mixer_ok:
            pygame.mixer.init()
            self._mixer_ok = True

    def _synth(self, text, voice):
        self._counter += 1
        path = os.path.join(tempfile.gettempdir(), f"fenix_tts_{os.getpid()}_{self._counter}.mp3")
        asyncio.run(_tts_async(text, voice, path))
        return path

    def _worker(self):
        while True:
            gen, text, voice = self._q.get()
            if gen != self._gen:
                continue
            self._speaking = True
            try:
                self._play_item(gen, text, voice)
            except Exception as e:
                print(f"[TTS HATASI] {e}")
            finally:
                if self._q.empty():
                    self._speaking = False

    def _play_item(self, gen, text, voice):
        parts = _chunks(text)
        if not parts:
            return
        self._ensure_mixer()
        with ThreadPoolExecutor(max_workers=1) as ex:
            fut = ex.submit(self._synth, parts[0], voice)
            for i in range(len(parts)):
                try:
                    path = fut.result()
                except Exception as e:
                    print(f"[TTS HATASI] {e}")
                    path = None
                if i + 1 < len(parts):
                    fut = ex.submit(self._synth, parts[i + 1], voice)   # sonrakini önceden hazırla
                if gen != self._gen:
                    self._rm(path)
                    return
                if not path:
                    continue
                try:
                    pygame.mixer.music.load(path)
                    pygame.mixer.music.play()
                    while pygame.mixer.music.get_busy() and gen == self._gen:
                        pygame.time.wait(50)
                    pygame.mixer.music.stop()
                    pygame.mixer.music.unload()
                except Exception as e:
                    print(f"[SES OYNATMA HATASI] {e}")
                self._rm(path)

    @staticmethod
    def _rm(path):
        try:
            if path:
                os.remove(path)
        except Exception:
            pass


_PLAYER = None


def _player():
    global _PLAYER
    if _PLAYER is None:
        _PLAYER = TTSPlayer()
    return _PLAYER


_PROSODY = {"rate": "+0%", "pitch": "+0Hz", "volume": "+0%"}


def set_prosody(rate=None, pitch=None, volume=None):
    """Konuşma hızı/tonu/yüksekliği (edge-tts biçimi: '+10%', '-5Hz')."""
    if rate:
        _PROSODY["rate"] = rate
    if pitch:
        _PROSODY["pitch"] = pitch
    if volume:
        _PROSODY["volume"] = volume


def get_prosody():
    return dict(_PROSODY)


async def _tts_async(text, voice, out_path):
    await edge_tts.Communicate(text, voice, rate=_PROSODY["rate"], pitch=_PROSODY["pitch"],
                               volume=_PROSODY["volume"]).save(out_path)


def speak(text, voice=DEFAULT_VOICE):
    """Kuyruğa ekler, beklemez."""
    try:
        from .i18n import tr
        text = tr(text, lines=False)
    except Exception:
        pass
    _player().speak(text, voice)


def stop_speaking():
    _player().stop()


def is_speaking():
    return _PLAYER is not None and _PLAYER.is_speaking()
