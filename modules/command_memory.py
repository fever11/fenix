# Core: MK-Agentic-System · Powered by FENIX Engine · (c) 2026 Mustafa Koç · All rights reserved
"""
Komut Hafızası (v5.9.0)
-----------------------
FENIX'in "ses aç" gibi sık komutlar için yapay zekâya sormadan çalışabilmesi.

Nasıl öğrenir?
  1) Yeni bir komutu ilk kez yapay zekâ çözer ve tek bir araç çağırır (ör. adjust_volume change=+10).
  2) Araç başarılı olduysa FENIX "bu cümle → bu araç + bu argümanlar" kaydını yapar. Cümledeki sayı ("sesi 40 yap")
     ve uygulama/klasör adı ("spotify'ı aç") yer tutucuya ({sayi}, {ad}) çevrilir; böylece her sayı ve her uygulama için
     ayrı kayıt gerekmez.
  3) Aynı anda hızlı bir model komutun başka söylenişlerini üretir ("sesi yükselt", "sesi arttır") ve onlar da kaydedilir.
  4) Sonraki seferde kod cümleyi hafızayla eşleştirir (küçük harf, Türkçe ek temizleme, yazı benzerliği) ve aracı doğrudan
     çalıştırır: API'ye gidilmez, cevap aracın kendi mesajıdır. Hazır cevap metni yoktur.

Güvenlik:
  - Yalnızca LEARNABLE listesindeki araçlar hafızadan çalışır; run_command, write_file, edit_file, delete_file,
    stop_process gibi serbest/yıkıcı araçlar ASLA. Onay isteyen araçlar (Wi-Fi'yi kapatma, uyku, zorla kapatma)
    hafızadan çalışsa da onay kutusu yine çıkar: onay aracın içindedir.
  - Cümlede kalıpta olmayan fazladan kelime varsa eşleşme olmaz ("sesi aç ama önce dosyayı sil" yapay zekâya gider).
  - Sadece başarıyla biten ve tek araç çağıran, kısa, "bunu/şunu/tekrar" gibi bağlama bağlı olmayan komutlar öğrenilir.
  - Uygulama/klasör adı kayıtlı envanterde yoksa hafıza çalışmaz, yapay zekâya gidilir.
  - Her kayıt "Öğrendiklerim" ekranından silinebilir; "yanlış anladın" demek son yerel çalışan kaydı siler.
"""
import os
import re
import json
import ntpath
import time
import hashlib
import difflib
import threading
import datetime

from . import functions as fx

PATH = os.path.join("data", "komut_hafizasi.json")
_LOCK = threading.RLock()
_CACHE = {"mtime": None, "data": None}

# Hafızadan doğrudan çalışabilecek araçlar (hepsi kısa, kullanıcıya doğrudan söylenebilecek bir mesaj döner)
LEARNABLE = {"set_system_volume", "adjust_volume", "set_brightness", "set_radio", "open_app_by_name", "close_app",
             "open_folder_by_name", "media_control", "power_action", "window_action", "open_url"}

# Araç -> metindeki ada karşılık gelen parametre ({ad} yer tutucusu)
NAME_PARAMS = {"open_app_by_name": "app_name", "close_app": "app_name", "open_folder_by_name": "folder_name",
               "window_action": "title"}

# ---------------------------------------------------------------- metin işleme
_FOLD = str.maketrans("çğıöşüâîû", "cgiosuaiu")
FILLER = {"lutfen", "hadi", "simdi", "yuzde", "bi", "bir", "bana", "benim", "hemen", "misin", "musun", "misiniz",
          "musunuz", "rica", "ederim", "edersen", "olur", "yapar", "yapabilir", "acaba", "ya"}
CONTEXT_WORDS = {"bunu", "sunu", "onu", "buna", "suna", "ona", "tekrar", "yine", "ayni", "bunlari", "sunlari",
                 "onlari", "oyle", "boyle", "gibi"}
# Birden çok isteği birbirine bağlayan sözcükler: yapay zekâ cümlenin bir kısmını yapıp geri kalanını atlamış olabilir,
# bu yüzden böyle cümleler bir kalıp olarak ÖĞRENİLMEZ
COMPOUND_WORDS = {"ve", "ile", "sonra", "ardindan", "ayrica", "hem", "ama", "fakat", "ancak", "veya", "once", "bide"}
PLACEHOLDERS = ("{sayi}", "{ad}")
_UNITS = {"sifir": 0, "iki": 2, "uc": 3, "dort": 4, "bes": 5, "alti": 6, "yedi": 7, "sekiz": 8, "dokuz": 9}
_TENS = {"yirmi": 20, "otuz": 30, "kirk": 40, "elli": 50, "altmis": 60, "yetmis": 70, "seksen": 80, "doksan": 90}
_SUF = sorted(["lari", "leri", "lar", "ler", "yi", "yu", "si", "su", "in", "un", "ni", "nu", "dan", "den", "tan", "ten",
               "da", "de", "ta", "te", "ya", "ye", "la", "le", "yla", "yle", "i", "u", "a", "e"],
              key=len, reverse=True)


def fold(t):
    """Küçük harf + Türkçe karakterler ASCII ('Görev Yöneticisi' -> 'gorev yoneticisi')."""
    return (t or "").replace("İ", "i").replace("I", "ı").lower().translate(_FOLD)


def _stem(tok):
    if len(tok) < 4 or tok.isdigit() or tok in PLACEHOLDERS:
        return tok
    for s in _SUF:
        if tok.endswith(s) and len(tok) - len(s) >= 3:
            return tok[:-len(s)]
    return tok


def tokens(text, template=False):
    """Metni karşılaştırılabilir parçalara ayırır.
    Döner: (kökler, katı_ascii_kelimeler, görünen_kelimeler, sayılar). Kullanıcı metninde sayılar ve sayı sözcükleri
    '{sayi}' olur (sayılar `sayılar` listesinde). template=True: metindeki '{sayi}' / '{ad}' yer tutucuları korunur;
    False: kullanıcı süslü parantez yazsa bile yer tutucu sayılmaz."""
    t = (text or "").replace("İ", "i").replace("I", "ı").lower().replace("’", "'").replace("`", "'")
    if not template:
        t = t.replace("{", " ").replace("}", " ")
    t = re.sub(r"'[a-zçğıöşü]*", " ", t)                    # spotify'ı -> spotify
    t = re.sub(r"(?<=[a-zçğıöşü])-(?=[a-zçğıöşü])", "", t)   # wi-fi -> wifi
    disp = re.findall(r"\{sayi\}|\{ad\}|[a-zçğıöşü0-9]+", t)
    raws, shown, nums = [], [], []
    i = 0
    while i < len(disp):
        d = disp[i]
        r = d if d in PLACEHOLDERS else fold(d)
        if template and d in PLACEHOLDERS:
            raws.append(d), shown.append(d)
        elif r.isdigit():
            raws.append("{sayi}"), shown.append("{sayi}"), nums.append(int(r))
        elif r in _TENS:
            val = _TENS[r]
            if i + 1 < len(disp) and fold(disp[i + 1]) in _UNITS and _UNITS[fold(disp[i + 1])] > 0:
                val += _UNITS[fold(disp[i + 1])]
                i += 1
            raws.append("{sayi}"), shown.append("{sayi}"), nums.append(val)
        elif r == "yuz":
            raws.append("{sayi}"), shown.append("{sayi}"), nums.append(100)
        elif r in _UNITS:
            raws.append("{sayi}"), shown.append("{sayi}"), nums.append(_UNITS[r])
        else:
            raws.append(r), shown.append(d)
        i += 1
    keep = [k for k, r in enumerate(raws) if r not in FILLER]
    raws = [raws[k] for k in keep]
    shown = [shown[k] for k in keep]
    return [_stem(r) for r in raws], raws, shown, nums


def _teq(a, b):
    if a == b:
        return True
    return min(len(a), len(b)) >= 5 and difflib.SequenceMatcher(None, a, b).ratio() >= 0.85


def _match(tmpl, stems, raws):
    """Kalıp, metnin TAMAMIYLA eşleşiyor mu? Döner: ({'ad': söylenen ad}, benzer_ama_aynı_olmayan_sayısı) ya da None."""
    best = [None]

    def rec(ti, ii, fz, slots):
        if ti == len(tmpl):
            if ii == len(stems) and (best[0] is None or fz < best[0][1]):
                best[0] = (dict(slots), fz)
            return
        tk = tmpl[ti]
        if tk == "{sayi}":
            if ii < len(stems) and stems[ii] == "{sayi}":
                rec(ti + 1, ii + 1, fz, slots)
        elif tk == "{ad}":
            for n in range(1, 5):
                span = raws[ii:ii + n]
                if len(span) < n or "{sayi}" in span:
                    break
                rec(ti + 1, ii + n, fz, dict(slots, ad=" ".join(span)))
        elif ii < len(stems) and stems[ii] not in PLACEHOLDERS and _teq(tk, stems[ii]):
            rec(ti + 1, ii + 1, fz + (0 if tk == stems[ii] else 1), slots)

    rec(0, 0, 0, {})
    return best[0]


# ---------------------------------------------------------------- depolama
def _empty():
    return {"surum": 1, "kayitlar": [], "egitim": {"tamam": {}, "son": ""}, "istatistik": {"yerel": 0}}


def load():
    with _LOCK:
        try:
            mt = os.path.getmtime(PATH)
        except OSError:
            return _empty()
        if _CACHE["mtime"] != mt:
            d = fx._load_json(PATH, None)
            base = _empty()
            if isinstance(d, dict):
                base.update({k: v for k, v in d.items() if k in base})
                if not isinstance(base["kayitlar"], list):
                    base["kayitlar"] = []
            _CACHE.update(mtime=mt, data=base)
        return _CACHE["data"]


def save(data):
    with _LOCK:
        fx._save_json(PATH, data)
        try:
            _CACHE.update(mtime=os.path.getmtime(PATH), data=data)
        except OSError:
            _CACHE.update(mtime=None, data=None)


def _now():
    return datetime.datetime.now().isoformat(timespec="seconds")


def _eid(kalip, arac, args):
    return hashlib.sha1(json.dumps([kalip, arac, args], sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:10]


def entries():
    return list(load()["kayitlar"])


def stats(schemas=None):
    d = load()
    out = {"kayit": len(d["kayitlar"]), "yerel": d["istatistik"].get("yerel", 0),
           "kullanimdan": sum(1 for e in d["kayitlar"] if e.get("kaynak") == "kullanim"),
           "egitimden": sum(1 for e in d["kayitlar"] if e.get("kaynak") == "egitim"),
           "uretilen": sum(1 for e in d["kayitlar"] if e.get("kaynak") == "uretilen")}
    if schemas is not None:
        out["egitim_bekleyen"] = pending_tools(schemas)
    return out


def remove(entry_id):
    with _LOCK:
        d = load()
        before = len(d["kayitlar"])
        d["kayitlar"] = [e for e in d["kayitlar"] if e.get("id") != entry_id]
        if len(d["kayitlar"]) != before:
            save(d)
            return True
        return False


def remove_matching(phrase):
    """Cümleyle eşleşen ya da görünen metni onu içeren kayıtları siler; silinen sayısını döner."""
    stems, _, _, _ = tokens(phrase)
    q = fold(phrase).strip()
    with _LOCK:
        d = load()
        keep, gone = [], 0
        for e in d["kayitlar"]:
            hit = (stems and e.get("kalip") == stems) or (q and q in fold(e.get("gorunen", "")))
            if hit:
                gone += 1
            else:
                keep.append(e)
        if gone:
            d["kayitlar"] = keep
            save(d)
        return gone


def clear_all():
    with _LOCK:
        d = load()
        n = len(d["kayitlar"])
        d["kayitlar"] = []
        d["egitim"] = {"tamam": {}, "son": ""}
        save(d)
        return n


def _add_entry(d, entry):
    """Kaydı ekler. Aynı kalıp ve aynı araç varsa: aynı argümanlarsa sayaç korunur (None döner); farklı argümanlarsa
    kullanıcıdan gelen yenisi eskinin yerine geçer (üretilen/eğitim kaydı kullanıcının öğrettiğini EZMEZ). Aynı kalıp
    başka araçlarda da olabilir ('{ad} aç' hem uygulama hem klasör); hangisinin çalışacağını ad doğrulaması belirler."""
    for old in d["kayitlar"]:
        if old["kalip"] == entry["kalip"] and old["arac"] == entry["arac"]:
            if old["args"] == entry["args"]:
                return None
            if old.get("kaynak") == "kullanim" and entry["kaynak"] != "kullanim":
                return None
            d["kayitlar"].remove(old)
            entry["sayac"] = old.get("sayac", 0)
            break
    d["kayitlar"].append(entry)
    return entry


def _make_entry(gorunen, kalip, arac, args, kaynak):
    return {"id": _eid(kalip, arac, args), "gorunen": gorunen, "kalip": kalip, "arac": arac, "args": args,
            "kaynak": kaynak, "sayac": 0, "olusturma": _now(), "son": ""}


# ---------------------------------------------------------------- argüman denetimi
_RANGES = {("set_system_volume", "level"): (0, 100), ("set_brightness", "level"): (1, 100),
           ("set_brightness", "change"): (-100, 100), ("adjust_volume", "change"): (-100, 100)}


def _in_range(arac, key, val):
    lo, hi = _RANGES.get((arac, key), (-1000, 1000))
    return isinstance(val, int) and not isinstance(val, bool) and lo <= val <= hi


def _resolve_name(arac, spoken):
    """Söylenen adı gerçek ada çevirir; envanter varsa ve ad orada yoksa '' (yapay zekâya git)."""
    from . import pc_tools
    if arac in ("open_app_by_name", "close_app"):
        return pc_tools.resolve_app(spoken)
    if arac == "open_folder_by_name":
        return pc_tools.resolve_folder(spoken)
    return spoken            # window_action title: söylenen kelimeler olduğu gibi


def _fill_args(entry, slots, nums):
    args = {}
    for k, v in entry["args"].items():
        if v in ("{sayi}", "-{sayi}"):
            if len(nums) != 1:
                return None
            val = nums[0] if v == "{sayi}" else -nums[0]
            if not _in_range(entry["arac"], k, val):
                return None
            args[k] = val
        elif v == "{ad}":
            real = _resolve_name(entry["arac"], slots.get("ad", ""))
            if not real:
                return None
            args[k] = real
        else:
            args[k] = v
    return args


# ---------------------------------------------------------------- eşleştirme ve çalıştırma
def find(text, allowed=None):
    """Metin hafızadaki bir komutla tamamen eşleşiyor mu? Döner: (kayıt, argümanlar) ya da None."""
    stems, raws, _, nums = tokens(text)
    if not stems or len(stems) > 10 or all(s in PLACEHOLDERS for s in stems):
        return None
    cands = []
    for e in load()["kayitlar"]:
        if e.get("arac") not in LEARNABLE or (allowed is not None and e["arac"] not in allowed):
            continue
        m = _match(e["kalip"], stems, raws)
        if m:
            cands.append((m[1], 0 if e.get("kaynak") == "kullanim" else 1, -e.get("sayac", 0), e, m[0]))
    for _, _, _, e, slots in sorted(cands, key=lambda c: c[:3]):
        args = _fill_args(e, slots, nums)
        if args is not None:
            return e, args
    return None


def execute(arac, args):
    """Aracı çalıştırır (aracın kendi konuşması kapalı: cevabı uygulama okur). Hata olursa None."""
    fn = fx.WHITELISTED_FUNCTIONS.get(arac)
    if not fn:
        return None
    old = fx._speak
    fx._speak = lambda *a, **k: None
    try:
        return fn(**args)
    except Exception as e:
        fx.report_error(f"komut hafızası: {arac}", e)
        return None
    finally:
        fx._speak = old


def result_ok(arac, result):
    """Araç gerçekten işi yaptı mı? (open_* araçları bulamayınca da status=ok dönüp 'BULUNAMADI' yazar.)"""
    if not isinstance(result, dict) or result.get("status") != "ok":
        return False
    return "BULUNAMADI" not in str(result.get("message", ""))


def reply_text(arac, args, result):
    """Yerel çalışmanın kullanıcıya söylenecek cevabı: aracın kendi mesajı. Bulunamadıysa None (yapay zekâya git)."""
    if not isinstance(result, dict):
        return None
    msg = str(result.get("message") or "").strip()
    st = result.get("status")
    if "BULUNAMADI" in msg:
        return None
    if st == "ok":
        m = re.match(r"Acildi:\s*(.+)", msg)
        if arac == "open_app_by_name" and m:
            return f"{m.group(1).strip()} açıldı."
        if arac == "open_folder_by_name" and m:
            return f"{ntpath.basename(m.group(1).strip().rstrip(chr(92) + '/')) or m.group(1)} klasörü açıldı."
        if arac == "open_url":
            host = re.sub(r"^https?://", "", str(args.get("url", ""))).split("/")[0]
            return f"{host} açıldı." if host else "Site açıldı."
        if arac == "set_system_volume":
            return f"Ses yüzde {args.get('level')} yapıldı."
        return msg or "Tamamlandı."
    if st in ("cancelled", "error") and msg:
        return msg
    return None


def record_use(entry_id):
    with _LOCK:
        d = load()
        d["istatistik"]["yerel"] = d["istatistik"].get("yerel", 0) + 1
        for e in d["kayitlar"]:
            if e["id"] == entry_id:
                e["sayac"] = e.get("sayac", 0) + 1
                e["son"] = _now()
        save(d)


# ---------------------------------------------------------------- kullanımdan öğrenme
def _args_learnable(arac, args):
    if not isinstance(args, dict):
        return False
    for k, v in args.items():
        if not isinstance(v, (str, int, bool)) or isinstance(v, float):
            return False
    if arac == "window_action" and args.get("action") == "list":
        return False
    if arac == "close_app" and args.get("force"):
        return False
    if arac == "open_url":
        u = str(args.get("url", ""))
        return bool(u) and "{" not in u and len(u) < 200
    return True


def _templatize(arac, args, stems, raws, shown, nums):
    """Cümleyi ve argümanları yer tutuculu kalıba çevirir. Döner: (kalıp, görünen, args) ya da None."""
    args2 = dict(args)
    st, rw, sh = list(stems), list(raws), list(shown)
    n = st.count("{sayi}")
    numeric = [k for k, v in args.items() if isinstance(v, int) and not isinstance(v, bool)]
    if n == 1:
        for k in numeric:
            if abs(args[k]) == nums[0]:
                args2[k] = "{sayi}" if args[k] >= 0 else "-{sayi}"
                break
        else:
            return None          # metindeki sayı argümanla ilgili değil: öğrenme
    elif n > 1:
        return None
    key = NAME_PARAMS.get(arac)
    if key and isinstance(args.get(key), str) and args[key].strip():
        aw = fold(args[key]).replace("-", " ").split()
        for i in range(len(rw) - len(aw) + 1):
            if all(rw[i + j] == aw[j] or _teq(rw[i + j], aw[j]) or _teq(_stem(rw[i + j]), _stem(aw[j]))
                   for j in range(len(aw))):
                st[i:i + len(aw)] = ["{ad}"]
                rw[i:i + len(aw)] = ["{ad}"]
                sh[i:i + len(aw)] = ["{ad}"]
                args2[key] = "{ad}"
                break
    return st, " ".join(sh), args2


def learn(text, calls, llm=None, mode_cfg=None, fast_model=None, sync=False):
    """Yapay zekânın az önce çözdüğü bir komutu hafızaya yazar (koşullar modül açıklamasında). Döner: kayıt ya da None."""
    try:
        if not isinstance(calls, (list, tuple)) or len(calls) != 1:
            return None
        arac, args, result = calls[0]
        if arac not in LEARNABLE or not result_ok(arac, result) or not _args_learnable(arac, args):
            return None
        if "?" in (text or "") or len(text or "") > 80:
            return None
        stems, raws, shown, nums = tokens(text)
        if not stems or len(stems) > 6 or set(raws) & (CONTEXT_WORDS | COMPOUND_WORDS):
            return None
        t = _templatize(arac, args, stems, raws, shown, nums)
        if not t:
            return None
        kalip, gorunen, args2 = t
        if not [s for s in kalip if s not in PLACEHOLDERS]:
            return None
        with _LOCK:
            d = load()
            e = _add_entry(d, _make_entry(gorunen, kalip, arac, args2, "kullanim"))
            if e is None:
                return None
            save(d)
        if llm is not None:
            def work():
                try:
                    add_paraphrases(e, llm, mode_cfg or {}, fast_model)
                except Exception as ex:
                    print(f"[KOMUT HAFIZASI] söylenişler üretilemedi: {ex}")
            if sync:
                work()
            else:
                threading.Thread(target=work, daemon=True).start()
        return e
    except Exception as ex:
        print(f"[KOMUT HAFIZASI] öğrenilemedi: {ex}")
        return None


# ---------------------------------------------------------------- yapay zekâdan söyleniş üretme
def _json_array(text):
    s = text or ""
    a, b = s.find("["), s.rfind("]")
    if a < 0 or b <= a:
        return []
    try:
        v = json.loads(s[a:b + 1])
        return v if isinstance(v, list) else []
    except Exception:
        return []


def _valid_phrase(p, need_sayi, need_ad):
    if not isinstance(p, str):
        return None
    p = re.sub(r"\s+", " ", p.strip().strip("\"'“”.!"))
    if not p or len(p) > 60 or "?" in p or len(p.split()) > 7:
        return None
    if p.count("{sayi}") != (1 if need_sayi else 0) or p.count("{ad}") != (1 if need_ad else 0):
        return None
    rest = p.replace("{sayi}", "").replace("{ad}", "")
    if "{" in rest or "}" in rest or re.search(r"\d", rest):
        return None
    return p


def add_paraphrases(entry, llm, mode_cfg, fast_model=None):
    """Kullanıcının öğrettiği komutun başka söylenişlerini hızlı modelle üretip kaydeder. Döner: eklenen sayısı."""
    sch = next((s for s in fx.FUNCTION_SCHEMAS if s["name"] == entry["arac"]), {})
    need_sayi = any(v in ("{sayi}", "-{sayi}") for v in entry["args"].values())
    need_ad = "{ad}" in entry["args"].values()
    prompt = (
        "Bir Türkçe masaüstü asistanına verilen şu komutun BAŞKA söylenişlerini yaz.\n"
        f"KOMUT: \"{entry['gorunen']}\"\nARAÇ: {entry['arac']} — {str(sch.get('description', ''))[:200]}\n"
        f"ARGÜMANLAR: {json.dumps(entry['args'], ensure_ascii=False)}\n"
        "Aynı anlama gelen, günlük konuşmada ya da sesli komutta söylenebilecek 10 kısa söyleniş ver (1-6 kelime; "
        "eş anlamlılar, farklı ekler). Anlamı DEĞİŞTİRME; zıt anlamlı söyleniş yazma."
        + (" Cümlede sayının yerine tam olarak {sayi} yaz." if need_sayi else " Cümlede sayı olmasın.")
        + (" Uygulama/klasör adının yerine tam olarak {ad} yaz." if need_ad else "")
        + "\nSADECE JSON dizisi döndür: [\"...\", \"...\"]")
    out = llm.complete(mode_cfg, prompt, fast=True, fast_model=fast_model, temperature=0.5, gemini_fallback=False)
    added = 0
    with _LOCK:
        d = load()
        for p in _json_array(out)[:14]:
            v = _valid_phrase(p, need_sayi, need_ad)
            if not v:
                continue
            stems, _, shown, _ = tokens(v, template=True)
            if not [s for s in stems if s not in PLACEHOLDERS]:
                continue
            if _add_entry(d, _make_entry(" ".join(shown), stems, entry["arac"], entry["args"], "uretilen")):
                added += 1
        if added:
            save(d)
    return added


# ---------------------------------------------------------------- eğitim turu
_HINTS = {
    "set_system_volume": (
        "Kesin ses seviyesi. args: {\"level\": 0-100}. Söylenişte sayı varsa soz'de {sayi}, args'ta \"level\": \"{sayi}\" "
        "(ör. soz \"sesi {sayi} yap\", \"ses {sayi} olsun\", \"sesi {sayi} seviyesine getir\"). Sayısız: 'sesi sıfırla / "
        "sessiz yap' level 0, 'sesi yarıya al' 50, 'sesi tam aç / son ses' 100."),
    "adjust_volume": (
        "Göreli ses. args: {\"change\": ±sayı} ve/veya {\"mute\": \"on|off|toggle\"}. Sayısız 'ses aç / sesi arttır / "
        "yükselt / ses yüksel / sesi büyüt' change 10; 'sesi kıs / azalt / düşür / ses azalsın' -10; 'biraz' ±10, "
        "'çok / bayağı' ±25. Sayılı: soz \"sesi {sayi} arttır\" → change \"{sayi}\"; soz \"sesi {sayi} azalt\" → "
        "change \"-{sayi}\". 'sustur / sesi kapat / sessize al' mute on; 'sessizi kapat / sesi geri aç / sesi aç "
        "(sessizdeyse)' mute off — ama 'ses aç' tek başına change 10 olsun (sessizse kendisi açar)."),
    "set_brightness": (
        "Ekran parlaklığı. args: {\"level\": 1-100} ya da {\"change\": ±sayı}. 'parlaklığı arttır/ekranı aydınlat' "
        "change 10, 'parlaklığı kıs/ekranı karart' -10, 'çok' ±25. Sayılı: \"parlaklığı {sayi} yap\" → level "
        "\"{sayi}\"; \"parlaklığı {sayi} arttır\" → change \"{sayi}\"; \"parlaklığı {sayi} azalt\" → change "
        "\"-{sayi}\". 'parlaklığı fulle / en yüksek' level 100, 'en düşük' level 5."),
    "set_radio": (
        "Wi-Fi/Bluetooth. args: {\"kind\": \"wifi|bluetooth\", \"state\": \"on|off|status\"}. 'wifi aç', "
        "'bluetooth'u kapat', 'kablosuz ağı aç', 'wifi açık mı' (status), 'bluetooth durumu'. Her kombinasyon için "
        "birkaç söyleniş yaz (6 kombinasyon)."),
    "open_app_by_name": (
        "Uygulama açma. args: {\"app_name\": \"{ad}\"}. Her soz'de {ad} tam bir kez olsun: \"{ad} aç\", \"{ad} uygulamasını "
        "aç\", \"{ad} başlat\", \"{ad} çalıştır\", \"{ad}'ı aç\" gibi."),
    "close_app": (
        "Uygulama kapatma. args: {\"app_name\": \"{ad}\"}. Her soz'de {ad} tam bir kez olsun: \"{ad} kapat\", \"{ad} "
        "uygulamasını kapat\", \"{ad}'dan çık\", \"{ad}'ı kapatır mısın\" gibi. force ASLA verme."),
    "open_folder_by_name": (
        "Klasör açma. args: {\"folder_name\": \"{ad}\"}. Her soz'de {ad} tam bir kez olsun: \"{ad} klasörünü aç\", "
        "\"{ad} klasörüne git\", \"{ad} dosyalarını göster\" gibi."),
    "media_control": (
        "Medya. args: {\"action\": \"play_pause|next|previous|stop\"}. 'müziği durdur / duraklat / devam et / oynat / "
        "şarkıyı başlat' play_pause; 'sonraki şarkı / parçayı geç / atla / ileri' next; 'önceki şarkı / geri sar / "
        "bir önceki' previous; stop yalnızca 'oynatıcıyı tamamen durdur' gibi."),
    "power_action": (
        "Güç. args: {\"action\": \"lock|screen_off|sleep\"}. 'ekranı kilitle / bilgisayarı kilitle' lock; 'ekranı kapat / "
        "monitörü kapat' screen_off; 'bilgisayarı uyut / uyku moduna al / uyu' sleep."),
    "window_action": (
        "Pencere. args: {\"action\": \"minimize_all|restore_all|minimize|maximize|restore|focus\", \"title\": \"{ad}\"}. "
        "title SADECE minimize/maximize/restore/focus için ve soz'de {ad} bir kez geçmeli: \"{ad} penceresini küçült\", "
        "\"{ad} ekranı kapla\", \"{ad} öne getir\". minimize_all: 'masaüstünü göster / tüm pencereleri küçült / hepsini "
        "küçült'; restore_all: 'pencereleri geri getir'. action 'list' KULLANMA."),
}
TRAIN_TOOLS = list(_HINTS)


def _sig(schema, name):
    return hashlib.sha1((json.dumps(schema, sort_keys=True, ensure_ascii=False) + _HINTS[name]).encode()).hexdigest()[:8]


MAX_ATTEMPTS = 3          # bir araç için kullanılabilir söyleniş üretilemezse en fazla bu kadar denenir


def pending_tools(schemas):
    eg = load()["egitim"]
    done, tries = eg.get("tamam", {}), eg.get("deneme", {})
    by = {s["name"]: s for s in schemas}
    return [n for n in TRAIN_TOOLS if n in by and done.get(n) != _sig(by[n], n) and tries.get(n, 0) < MAX_ATTEMPTS]


_NAME_KEYS = {"app_name", "folder_name", "title"}


def _valid_item(arac, schema, item):
    """Eğitim turunda üretilen {'soz', 'args'} öğesini doğrular. Döner: (soz, args) ya da None."""
    if not isinstance(item, dict) or not isinstance(item.get("args"), dict):
        return None
    props = (schema.get("parameters") or {}).get("properties", {})
    req = (schema.get("parameters") or {}).get("required", [])
    args = {}
    uses_sayi = uses_ad = False
    for k, v in item["args"].items():
        spec = props.get(k)
        if spec is None:
            return None
        t = spec.get("type")
        if t == "integer":
            if v in ("{sayi}", "-{sayi}"):
                if v == "-{sayi}" and arac not in ("adjust_volume", "set_brightness"):
                    return None
                uses_sayi = True
            elif not _in_range(arac, k, v):
                return None
        elif t == "string":
            if k in _NAME_KEYS:
                if v != "{ad}":
                    return None
                uses_ad = True
            elif "enum" in spec:
                if v not in spec["enum"]:
                    return None
            else:
                return None
        elif t == "boolean":
            if v is not False:
                return None
        else:
            return None
        args[k] = v
    if any(r not in args for r in req):
        return None
    if arac == "window_action":
        a = args.get("action")
        if a == "list" or (a in ("minimize", "maximize", "restore", "focus")) != ("title" in args):
            return None
    if arac == "set_brightness" and len([k for k in args if k in ("level", "change")]) != 1:
        return None
    if arac == "adjust_volume" and not args:
        return None
    soz = _valid_phrase(item.get("soz"), uses_sayi, uses_ad)
    return (soz, args) if soz else None


def train(llm, mode_cfg, schemas, fast_model=None, cancelled=None, on_progress=None, max_tools=20, pause=1.0):
    """Bekleyen araçlar için söylenişleri üretir ve kaydeder (araç başına bir hızlı-model isteği; yalnızca Groq).
    Kota/ağ hatasında durur, kalanlar sonraki sefere kalır. Döner: {'eklenen', 'kalan', 'durdu'}."""
    by = {s["name"]: s for s in schemas}
    todo = pending_tools(schemas)[:max_tools]
    total_added, stopped = 0, ""
    for name in todo:
        if cancelled and cancelled():
            stopped = "durduruldu"
            break
        sch = by[name]
        prompt = (
            "Bir Türkçe masaüstü asistanı (FENIX) için komut kalıpları üret.\n"
            f"ARAÇ: {name}\nAÇIKLAMA: {sch['description']}\n"
            f"PARAMETRELER: {json.dumps((sch.get('parameters') or {}).get('properties', {}), ensure_ascii=False)}\n"
            f"KURALLAR: {_HINTS[name]}\n"
            "ÇIKTI: SADECE bir JSON dizisi; her eleman {\"soz\": \"...\", \"args\": {...}}. 20-26 eleman. Söylenişler "
            "gündelik konuşma ya da sesli komut gibi KISA (1-6 kelime) ve birbirinden FARKLI olsun (eş anlamlılar, farklı "
            "ekler, kısa-uzun). Yer tutucular: sayı için {sayi}, uygulama/klasör/pencere adı için {ad}; soz içinde AYNEN bu "
            "biçimde yaz, başka yer tutucu uydurma. Sayıyı soz'e rakam olarak yazma.")
        try:
            out = llm.complete(mode_cfg, prompt, fast=True, fast_model=fast_model, temperature=0.5,
                               gemini_fallback=False)
        except Exception as e:
            stopped = f"{type(e).__name__}: {str(e)[:100]}"
            break
        added = 0
        with _LOCK:
            d = load()
            for item in _json_array(out):
                v = _valid_item(name, sch, item)
                if not v:
                    continue
                soz, args = v
                stems, _, shown, _ = tokens(soz, template=True)
                if not [s for s in stems if s not in PLACEHOLDERS]:
                    continue
                if _add_entry(d, _make_entry(" ".join(shown), stems, name, args, "egitim")):
                    added += 1
            if added:
                d["egitim"].setdefault("tamam", {})[name] = _sig(sch, name)
                d["egitim"]["son"] = _now()
            else:
                tr = d["egitim"].setdefault("deneme", {})
                tr[name] = tr.get(name, 0) + 1
                stopped = f"{name}: kullanılabilir söyleniş üretilemedi"
            save(d)
        total_added += added
        if on_progress:
            try:
                on_progress(name, added)
            except Exception:
                pass
        if pause:
            time.sleep(pause)
    return {"eklenen": total_added, "kalan": pending_tools(schemas), "durdu": stopped}


def summary_text(schemas=None, limit=12):
    """Sohbette gösterilecek kısa özet."""
    st = stats(schemas)
    lines = [f"Hafızamda {st['kayit']} komut kalıbı var ({st['kullanimdan']} senin öğrettiğin, {st['uretilen']} "
             f"ürettiğim söyleniş, {st['egitimden']} eğitim turundan). Yapay zekâya gitmeden {st['yerel']} kez çalıştırdım."]
    top = sorted(load()["kayitlar"], key=lambda e: (-e.get("sayac", 0), e.get("kaynak") != "kullanim"))[:limit]
    if top:
        lines.append("Örnekler: " + "; ".join(f"\"{e['gorunen']}\" → {e['arac']}" for e in top))
    if st.get("egitim_bekleyen"):
        lines.append(f"Eğitim turu bekleyen araçlar: {', '.join(st['egitim_bekleyen'])} ('kendini eğit' dersen üretirim).")
    return "\n".join(lines)
