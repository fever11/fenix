# Core: MK-Agentic-System · Powered by FENIX Engine · (c) 2026 Mustafa Koç · GPL-3.0-only (LICENSE, NOTICE.md)
"""FENIX dil desteği / language support (TR, EN, DE, RU, FR, ES).

Kaynak dil Türkçedir: arayüz metinleri kodda Türkçe yazılıdır. Seçilen dil Türkçe değilse metinler
locales/<dil>.json sözlüğünden çevrilir; sözlükte olmayan metin olduğu gibi (Türkçe) kalır.

The source language is Turkish: UI strings are written in Turkish in the code. When another language is
selected, strings are translated through locales/<lang>.json; anything missing falls back to Turkish.

Çeviri iki yoldan yapılır / Two ways strings get translated:
  1) tr("metin")                  – doğrudan çağrı / explicit call
  2) install_tk_hooks()           – CustomTkinter/Tk pencere metinleri (text=, title, menü, mesaj kutusu, metin
                                    kutusu) otomatik çevrilir / widget texts are translated automatically
Biçimli metinler için sözlükte "templates" vardır: "Mod değişti: {}" -> "Mode changed: {}".
"""
import json
import locale
import os
import re

LANGS = {"tr": "Türkçe", "en": "English", "de": "Deutsch", "ru": "Русский", "fr": "Français", "es": "Español"}
LANG_NAMES_EN = {"tr": "Turkish", "en": "English", "de": "German", "ru": "Russian", "fr": "French", "es": "Spanish"}

# edge-tts sesleri (erkek, doğal) / edge-tts voices
TTS_VOICES = {"tr": "tr-TR-AhmetNeural", "en": "en-US-GuyNeural", "de": "de-DE-ConradNeural",
              "ru": "ru-RU-DmitryNeural", "fr": "fr-FR-HenriNeural", "es": "es-ES-AlvaroNeural"}
# Ses tanıma kodları / speech recognition codes (Whisper, Google)
STT_WHISPER = {"tr": "tr", "en": "en", "de": "de", "ru": "ru", "fr": "fr", "es": "es"}
STT_GOOGLE = {"tr": "tr-TR", "en": "en-US", "de": "de-DE", "ru": "ru-RU", "fr": "fr-FR", "es": "es-ES"}

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOCALE_DIR = os.path.join(_ROOT, "locales")

_state = {"lang": "tr", "strings": {}, "templates": []}


# ------------------------------------------------------------------ dil seçimi / language selection
def system_language():
    """İşletim sisteminin dili desteklenen dillerden biriyse onu döner, değilse 'en'."""
    try:
        code = (locale.getlocale()[0] or locale.getdefaultlocale()[0] or "").lower()
    except Exception:
        code = ""
    for k in LANGS:
        if code.startswith(k):
            return k
    return "en" if code else "tr"


def detect(cfg=None):
    """Öncelik: data/ayarlar.json (uygulamadan seçilen) > config.yaml 'language' > sistem dili."""
    try:
        from . import user_settings
        v = (user_settings.get("language") or "").lower()
        if v in LANGS:
            return v
    except Exception:
        pass
    v = str((cfg or {}).get("language") or "").lower()
    if v in LANGS:
        return v
    return system_language()


def set_language(code):
    code = (code or "tr").lower()
    if code not in LANGS:
        code = "tr"
    _state["lang"] = code
    _state["strings"], _state["templates"], _state["tools"] = {}, [], {}
    if code == "tr":
        return code
    path = os.path.join(LOCALE_DIR, f"{code}.json")
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"[DİL] {path} okunamadı: {e}")
        return code
    _state["strings"] = data.get("strings", {})
    _state["tools"] = data.get("tools", {})
    tpls = []
    for src, dst in (data.get("templates") or {}).items():
        parts = src.split("{}")
        pat = "(.+?)".join(re.escape(p) for p in parts)
        try:
            tpls.append((re.compile(pat + r"\Z", re.S), dst, len(parts) - 1))
        except re.error:
            pass
    tpls.sort(key=lambda x: -len(x[0].pattern))      # uzun (daha özel) kalıplar önce
    _state["templates"] = tpls
    return code


def init(cfg=None):
    """Uygulama açılışında çağrılır: dili belirler, sözlüğü yükler, sesi dile uydurur."""
    code = set_language(detect(cfg))
    if cfg is not None:
        apply_to_config(cfg)
    return code


def save_language(code):
    """Uygulama içinden seçilen dili kalıcı kaydeder (bir sonraki açılışta geçerli olur)."""
    from . import user_settings
    user_settings.set("language", code if code in LANGS else "tr")


def lang():
    return _state["lang"]


def apply_to_config(cfg):
    """Seçilen dil Türkçe değilse ve config'teki ses başka dildeyse, sesi seçilen dilin sesine çevirir."""
    audio = cfg.setdefault("audio", {})
    voice = audio.get("tts_voice") or ""
    want = TTS_VOICES[_state["lang"]]
    if not voice.lower().startswith(want[:2].lower() + "-"):
        audio["tts_voice"] = want
    return cfg


def stt_whisper():
    return STT_WHISPER[_state["lang"]]


def stt_google():
    return STT_GOOGLE[_state["lang"]]


def reply_rule():
    """Yapay zekâya hangi dilde cevap vereceğini söyleyen kural (sistem talimatının sonuna eklenir)."""
    name = LANG_NAMES_EN[_state["lang"]]
    if _state["lang"] == "tr":
        return "DİL: Kullanıcıya HER ZAMAN Türkçe cevap ver."
    return (f"LANGUAGE: The user's interface language is {name}. ALWAYS write every reply, report, summary and "
            f"message meant for the user in {name}, even though these instructions are written in Turkish. "
            f"Keep code, file names, commands and JSON keys unchanged.")


# ------------------------------------------------------------------ çeviri / translation
def _exact(s):
    d = _state["strings"]
    if s in d:
        return d[s]
    core = s.strip()
    if core and core != s and core in d:
        i = s.index(core)
        return s[:i] + d[core] + s[i + len(core):]
    return None


def _template(s):
    core = s.strip()
    if not core:
        return None
    for rx, dst, n in _state["templates"]:
        m = rx.match(core)
        if m:
            args = [tr(g, lines=False) for g in m.groups()]     # parçalar da çevrilir (iç içe kalıplar)
            try:
                out = dst.format(*args)
            except Exception:
                continue
            i = s.index(core)
            return s[:i] + out + s[i + len(core):]
    return None


def tr(text, lines=True):
    """Metni seçili dile çevirir. Bulunamazsa olduğu gibi döner.
    lines=True: çok satırlı metinde satır satır da dener (yardım pencereleri için)."""
    if _state["lang"] == "tr" or not isinstance(text, str) or not text:
        return text
    out = _exact(text)
    if out is not None:
        return out
    out = _template(text)
    if out is not None:
        return out
    if lines and "\n" in text:
        parts = text.split("\n")
        new = [tr(p, lines=False) for p in parts]
        if new != parts:
            return "\n".join(new)
    return text


def tool_desc(name, default):
    """Araç açıklaması (Yetenekler penceresi). Sözlükte 'tools' bölümünde yoksa Türkçe hali döner."""
    if _state["lang"] == "tr":
        return default
    return _state.get("tools", {}).get(name, default)


def tr_values(values):
    return [tr(v) for v in values]


def mark_raw(textbox):
    """Sohbet kutusu gibi serbest metin alanlarını otomatik çeviriden muaf tutar (çeviri elle yapılır)."""
    for w in (textbox, getattr(textbox, "_textbox", None)):
        if w is not None:
            try:
                w._i18n_raw = True
            except Exception:
                pass
    return textbox


# ------------------------------------------------------------------ arayüz kancaları / UI hooks
_TEXT_KEYS = ("text", "placeholder_text", "label_text", "title", "message")
_installed = [False]


def _wrap_kwargs(kw):
    for k in _TEXT_KEYS:
        if k in kw and isinstance(kw[k], str):
            kw[k] = tr(kw[k])
    return kw


def install_tk_hooks():
    """CustomTkinter ve Tk metinlerini otomatik çevirir. Türkçe seçiliyken hiçbir şey yapmaz."""
    if _state["lang"] == "tr" or _installed[0]:
        return
    _installed[0] = True
    import tkinter
    from tkinter import messagebox
    import customtkinter as ctk

    classes = [getattr(ctk, n) for n in ("CTkLabel", "CTkButton", "CTkCheckBox", "CTkSwitch", "CTkRadioButton",
                                         "CTkEntry", "CTkScrollableFrame", "CTkInputDialog", "CTkTabview")
               if hasattr(ctk, n)]
    for cls in classes:
        orig_init = cls.__init__

        def init(self, *a, __o=orig_init, **kw):
            __o(self, *a, **_wrap_kwargs(kw))
        cls.__init__ = init
        if hasattr(cls, "configure"):
            orig_conf = cls.configure

            def conf(self, *a, __o=orig_conf, **kw):
                return __o(self, *a, **_wrap_kwargs(kw))
            cls.configure = conf

    # pencere başlıkları / window titles
    orig_title = tkinter.Wm.wm_title

    def wm_title(self, string=None):
        return orig_title(self, tr(string) if isinstance(string, str) else string)
    tkinter.Wm.wm_title = wm_title
    tkinter.Wm.title = wm_title
    for cls in (ctk.CTk, ctk.CTkToplevel):
        if "title" in cls.__dict__ or "wm_title" in cls.__dict__:
            o = cls.__dict__.get("title") or cls.__dict__.get("wm_title")

            def t2(self, string=None, __o=o):
                return __o(self, tr(string) if isinstance(string, str) else string)
            if "title" in cls.__dict__:
                cls.title = t2
            if "wm_title" in cls.__dict__:
                cls.wm_title = t2

    # menüler / menus
    for meth in ("add_command", "add_checkbutton", "add_radiobutton", "add_cascade"):
        o = getattr(tkinter.Menu, meth)

        def m(self, cnf=None, __o=o, **kw):
            if "label" in kw and isinstance(kw["label"], str):
                kw["label"] = tr(kw["label"])
            return __o(self, cnf or {}, **kw)
        setattr(tkinter.Menu, meth, m)

    # mesaj kutuları / message boxes
    for name in ("showinfo", "showwarning", "showerror", "askyesno", "askokcancel", "askyesnocancel",
                 "askquestion", "askretrycancel"):
        o = getattr(messagebox, name)

        def mb(title=None, message=None, __o=o, **kw):
            return __o(tr(title) if isinstance(title, str) else title,
                       tr(message) if isinstance(message, str) else message, **kw)
        setattr(messagebox, name, mb)

    # metin kutuları (yardım/durum pencereleri) / text boxes
    orig_ins = tkinter.Text.insert

    def ins(self, index, chars, *args):
        if getattr(self, "_i18n_raw", False):          # sohbet kutusu: kullanıcı/model metni olduğu gibi kalır
            return orig_ins(self, index, chars, *args)
        return orig_ins(self, index, tr(chars) if isinstance(chars, str) else chars, *args)
    tkinter.Text.insert = ins
    if hasattr(ctk, "CTkTextbox"):
        o = ctk.CTkTextbox.insert

        def cins(self, index, text, tags=None, __o=o):
            if getattr(self, "_i18n_raw", False):
                return __o(self, index, text, tags)
            return __o(self, index, tr(text) if isinstance(text, str) else text, tags)
        ctk.CTkTextbox.insert = cins
