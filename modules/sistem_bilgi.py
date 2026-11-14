# Core: MK-Agentic-System · Powered by FENIX Engine · (c) 2026 Mustafa Koç · GPL-3.0-only (LICENSE, NOTICE.md)
"""Sistem paneli verileri (v1.4). Arayüzden bağımsızdır, test edilebilir.

Hepsi yerel okumadır: yapay zekâ ve internet kullanılmaz, kota harcamaz. Okuma maliyeti düşüktür (psutil); pil
raporu ve en büyük dosyalar gibi yavaş işler önbelleğe alınır.
"""
import json
import os
import re
import shutil
import subprocess
import time

try:
    import psutil
except Exception:          # pragma: no cover
    psutil = None

DATA_DIR = "data"
OLAY_DOSYA = os.path.join(DATA_DIR, "guvenlik_olaylari.jsonl")
PIL_ONBELLEK = os.path.join(DATA_DIR, "pil_saglik.json")
_SON_AG = {"t": None, "gonderilen": 0, "alinan": 0}


def _mb(b):
    return round(b / 1024 / 1024)


def _gb(b):
    return round(b / 1024 ** 3, 1)


# ------------------------------------------------------------------ anlık durum
def anlik():
    """CPU, RAM, disk, ağ ve (varsa) NVIDIA ekran kartı. Her alan okunamazsa None."""
    out = {"cpu": None, "ram": None, "diskler": [], "ag": None, "gpu": None}
    if not psutil:
        return out
    try:
        out["cpu"] = psutil.cpu_percent(interval=None)
    except Exception:
        pass
    try:
        v = psutil.virtual_memory()
        out["ram"] = {"yuzde": v.percent, "kullanilan_gb": _gb(v.used), "toplam_gb": _gb(v.total)}
    except Exception:
        pass
    out["diskler"] = diskler()
    out["ag"] = ag_hizi()
    out["gpu"] = gpu()
    return out


def diskler():
    sonuc = []
    try:
        for p in psutil.disk_partitions(all=False):
            if os.name == "nt" and ("cdrom" in (p.opts or "") or not p.fstype):
                continue
            try:
                u = psutil.disk_usage(p.mountpoint)
            except Exception:
                continue
            if u.total < 1024 ** 3:          # 1 GB'tan küçük sistem/sanal bölümler gösterilmez
                continue
            sonuc.append({"ad": p.mountpoint, "yuzde": u.percent, "bos_gb": _gb(u.free), "toplam_gb": _gb(u.total)})
    except Exception:
        pass
    return sonuc[:6]


def ag_hizi():
    """Son çağrıdan bu yana yükleme/indirme hızı (Mbit/sn). İlk çağrı 0 döner."""
    try:
        c = psutil.net_io_counters()
    except Exception:
        return None
    t = time.time()
    once = dict(_SON_AG)
    _SON_AG.update(t=t, gonderilen=c.bytes_sent, alinan=c.bytes_recv)
    if not once["t"] or t - once["t"] <= 0:
        return {"yukleme": 0.0, "indirme": 0.0}
    dt = t - once["t"]
    return {"yukleme": round((c.bytes_sent - once["gonderilen"]) * 8 / dt / 1e6, 1),
            "indirme": round((c.bytes_recv - once["alinan"]) * 8 / dt / 1e6, 1)}


_GPU_YOK = {"t": 0}


def gpu():
    """NVIDIA ekran kartı: kullanım, sıcaklık, bellek (nvidia-smi). Yoksa None; 10 dk tekrar denenmez."""
    if time.time() - _GPU_YOK["t"] < 600:
        return None
    exe = shutil.which("nvidia-smi")
    if not exe:
        _GPU_YOK["t"] = time.time()
        return None
    try:
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        r = subprocess.run([exe, "--query-gpu=name,utilization.gpu,temperature.gpu,memory.used,memory.total",
                            "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=3,
                           creationflags=flags)
        ad, kul, sic, mu, mt = [x.strip() for x in r.stdout.strip().splitlines()[0].split(",")]
        return {"ad": ad, "yuzde": float(kul), "sicaklik": float(sic), "bellek_mb": float(mu), "bellek_toplam_mb": float(mt)}
    except Exception:
        _GPU_YOK["t"] = time.time()
        return None


def en_cok_kullananlar(n=5, sirala="ram"):
    """En çok RAM (ya da CPU) kullanan programlar. Aynı adlı süreçler toplanır (ör. tarayıcı sekmeleri)."""
    if not psutil:
        return []
    toplam = {}
    for p in psutil.process_iter(["pid", "name", "memory_info", "cpu_percent"]):
        try:
            ad = p.info["name"] or "?"
            if ad.lower() in ("system idle process", "idle", "system", "registry", "memory compression"):
                continue
            t = toplam.setdefault(ad, {"ad": ad, "ram_mb": 0, "cpu": 0.0, "pid": p.info["pid"], "adet": 0})
            t["ram_mb"] += _mb(p.info["memory_info"].rss) if p.info["memory_info"] else 0
            t["cpu"] += p.info["cpu_percent"] or 0.0
            t["adet"] += 1
        except Exception:
            continue
    anahtar = (lambda x: x["cpu"]) if sirala == "cpu" else (lambda x: x["ram_mb"])
    return sorted(toplam.values(), key=anahtar, reverse=True)[:n]


# ------------------------------------------------------------------ pil
def pil():
    """Şarj yüzdesi ve prizde mi; sağlık (tasarım kapasitesine göre) günde bir kez okunur."""
    out = {"yuzde": None, "prizde": None, "saglik": None}
    try:
        b = psutil.sensors_battery()
        if b is None:
            return None                       # masaüstü bilgisayar: pil yok
        out["yuzde"], out["prizde"] = round(b.percent), bool(b.power_plugged)
    except Exception:
        return None
    out["saglik"] = pil_sagligi()
    return out


def pil_sagligi(zorla=False):
    """Windows pil raporundan: tam şarj kapasitesi / tasarım kapasitesi (%). Günde bir kez; yönetici izni gerekmez."""
    try:
        with open(PIL_ONBELLEK, encoding="utf-8") as f:
            o = json.load(f)
        if not zorla and time.time() - o.get("t", 0) < 86400:
            return o.get("saglik")
    except Exception:
        pass
    if os.name != "nt":
        return None
    yol = os.path.abspath(os.path.join(DATA_DIR, "pil_raporu.xml"))
    try:
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        subprocess.run(["powercfg", "/batteryreport", "/xml", "/output", yol], capture_output=True, timeout=20,
                       creationflags=flags)
        with open(yol, encoding="utf-8", errors="ignore") as f:
            xml = f.read()
        saglik = pil_xml_coz(xml)
    except Exception:
        saglik = None
    finally:
        try:
            os.remove(yol)
        except OSError:
            pass
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(PIL_ONBELLEK, "w", encoding="utf-8") as f:
            json.dump({"t": time.time(), "saglik": saglik}, f)
    except Exception:
        pass
    return saglik


def pil_xml_coz(xml):
    tas = re.search(r"<DesignCapacity>(\d+)</DesignCapacity>", xml or "")
    tam = re.search(r"<FullChargeCapacity>(\d+)</FullChargeCapacity>", xml or "")
    if not tas or not tam or int(tas.group(1)) <= 0:
        return None
    t, f = int(tas.group(1)), int(tam.group(1))
    return {"yuzde": round(min(100.0, f * 100.0 / t)), "tasarim_mwh": t, "tam_sarj_mwh": f}


# ------------------------------------------------------------------ güvenlik olayları (Nöbet)
def olay_kaydet(ev):
    """Nöbet/gözcü uyarısını kaydeder (son 200 tutulur)."""
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        k = {"zaman": time.time(), "seviye": ev.get("seviye"), "baslik": ev.get("baslik"),
             "kisa": ev.get("kisa") or ev.get("metin"), "kaynak": ev.get("kaynak")}
        with open(OLAY_DOSYA, "a", encoding="utf-8") as f:
            f.write(json.dumps(k, ensure_ascii=False) + "\n")
        with open(OLAY_DOSYA, encoding="utf-8") as f:
            satirlar = f.readlines()
        if len(satirlar) > 400:
            with open(OLAY_DOSYA, "w", encoding="utf-8") as f:
                f.writelines(satirlar[-200:])
    except Exception:
        pass


def son_olaylar(n=10):
    try:
        with open(OLAY_DOSYA, encoding="utf-8") as f:
            satirlar = f.readlines()
    except Exception:
        return []
    out = []
    for s in reversed(satirlar):
        try:
            out.append(json.loads(s))
        except Exception:
            continue
        if len(out) >= n:
            break
    return out


# ------------------------------------------------------------------ sağlık raporu
def en_buyuk_dosyalar(klasorler=None, n=10, en_fazla_dosya=40000, sure=8.0):
    """Kullanıcı klasörlerindeki en büyük dosyalar (süre ve dosya sayısı sınırlı tarama)."""
    ev = os.path.expanduser("~")
    klasorler = klasorler or [os.path.join(ev, k) for k in ("Downloads", "Desktop", "Documents", "Videos")]
    bitis, sayac, liste = time.time() + sure, 0, []
    for kok_klasor in klasorler:
        for kok, dirs, files in os.walk(kok_klasor):
            dirs[:] = [d for d in dirs if not d.startswith(".") and d.lower() not in ("node_modules", "__pycache__")]
            for d in files:
                sayac += 1
                if sayac > en_fazla_dosya or time.time() > bitis:
                    break
                try:
                    yol = os.path.join(kok, d)
                    liste.append((os.path.getsize(yol), yol))
                except OSError:
                    pass
            if sayac > en_fazla_dosya or time.time() > bitis:
                break
    liste.sort(reverse=True)
    return [{"yol": y, "boyut_gb": round(b / 1024 ** 3, 2)} for b, y in liste[:n]]


def baslangic_programlari():
    try:
        from . import functions as fx
        return fx._startup_entries()
    except Exception:
        return []


def saglik_raporu(buyuk_dosyalar=True):
    """Türkçe, sade sağlık raporu metni (yapay zekâ kullanmadan)."""
    a = anlik()
    satir = [f"FENIX Bilgisayar Sağlık Raporu · {time.strftime('%d.%m.%Y %H:%M')}", ""]
    uyarilar = []
    satir.append("DİSKLER")
    for d in a["diskler"]:
        durum = "dolmak üzere" if d["yuzde"] >= 90 else "dolu sayılır" if d["yuzde"] >= 80 else "iyi"
        satir.append(f"  {d['ad']}  %{d['yuzde']:.0f} dolu · {d['bos_gb']} GB boş / {d['toplam_gb']} GB ({durum})")
        if d["yuzde"] >= 90:
            uyarilar.append(f"{d['ad']} sürücüsü %{d['yuzde']:.0f} dolu; yer açmak bilgisayarı hızlandırır.")
    if a["ram"]:
        r = a["ram"]
        satir += ["", "BELLEK (RAM)", f"  %{r['yuzde']:.0f} kullanımda · {r['kullanilan_gb']} / {r['toplam_gb']} GB"]
        if r["yuzde"] >= 85:
            uyarilar.append("RAM %85'in üstünde; açık programları azaltmak iyi olur.")
    progs = en_cok_kullananlar(5)
    if progs:
        satir += ["", "EN ÇOK RAM KULLANANLAR"]
        satir += [f"  {p['ad']}" + (f" ({p['adet']} süreç)" if p["adet"] > 1 else "") + f" · {p['ram_mb']} MB"
                  for p in progs]
    p = pil()
    if p:
        satir += ["", "PİL", f"  %{p['yuzde']} · {'prizde' if p['prizde'] else 'pilde'}"]
        if p.get("saglik"):
            s = p["saglik"]
            satir.append(f"  Sağlık: %{s['yuzde']} (tam şarj kapasitesi / fabrika kapasitesi)")
            if s["yuzde"] < 70:
                uyarilar.append(f"Pil sağlığı %{s['yuzde']}; pil eskimiş, değişim düşünülebilir.")
    if a["gpu"]:
        g = a["gpu"]
        satir += ["", "EKRAN KARTI", f"  {g['ad']} · %{g['yuzde']:.0f} kullanım · {g['sicaklik']:.0f} °C"]
    bas = baslangic_programlari()
    if bas:
        satir += ["", f"AÇILIŞTA BAŞLAYAN PROGRAMLAR ({len(bas)})"]
        satir += [f"  {b.get('ad') or b.get('name') or b}" for b in bas[:15]]
        if len(bas) > 12:
            uyarilar.append(f"Açılışta {len(bas)} program başlıyor; gereksizleri kapatmak açılışı hızlandırır "
                            "(\"açılışta başlayanlardan X'i kaldır\" diyebilirsin, geri alınabilir).")
    olaylar = son_olaylar(10)
    satir += ["", "SON GÜVENLİK OLAYLARI (Nöbet)"]
    if olaylar:
        satir += [f"  {time.strftime('%d.%m %H:%M', time.localtime(o['zaman']))} · {o.get('kisa') or o.get('baslik')}"
                  for o in olaylar]
    else:
        satir.append("  Kayıtlı olay yok.")
    if buyuk_dosyalar:
        bd = en_buyuk_dosyalar()
        if bd:
            satir += ["", "EN BÜYÜK DOSYALAR (İndirilenler, Masaüstü, Belgeler, Videolar)"]
            satir += [f"  {d['boyut_gb']} GB · {d['yol']}" for d in bd]
    ozet = ["ÖZET"] + ([f"  • {u}" for u in uyarilar] or ["  • Önemli bir sorun görünmüyor."]) + [""]
    return "\n".join(satir[:2] + ozet + satir[2:])
