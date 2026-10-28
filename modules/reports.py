# Core: MK-Agentic-System · Powered by FENIX Engine · (c) 2026 Mustafa Koç · All rights reserved
"""
Rapor Deposu (Raporlarım)
-------------------------
Derin araştırma / site denetimi raporları data/raporlar/ altında tutulur.

Yer tasarrufu (config.yaml -> reports):
- compress_after_days : bu kadar günden eski raporlar gzip ile sıkıştırılır (.md.gz, ~%70 küçülür)
- max_count           : en fazla rapor sayısı; aşılırsa en eski SABİTLENMEMİŞ raporlar silinir
- max_total_mb        : toplam boyut sınırı; aşılırsa yine en eskiden silinir
Sabitlenen (📌) raporlar hiçbir zaman otomatik silinmez veya sıkıştırılmaz.
"""
import os
import re
import gzip
import json
import time
import datetime

DEFAULTS = {"max_count": 100, "max_total_mb": 50, "compress_after_days": 7}


class ReportStore:
    def __init__(self, folder="data/raporlar", cfg=None):
        self.folder = folder
        self.cfg = dict(DEFAULTS, **(cfg or {}))
        self.pins_path = os.path.join(folder, "sabitlenenler.json")

    # ---------------- sabitleme ----------------
    def _pins(self):
        try:
            with open(self.pins_path, encoding="utf-8") as f:
                return set(json.load(f))
        except Exception:
            return set()

    def _save_pins(self, pins):
        os.makedirs(self.folder, exist_ok=True)
        with open(self.pins_path, "w", encoding="utf-8") as f:
            json.dump(sorted(pins), f, ensure_ascii=False, indent=1)

    @staticmethod
    def _key(path):
        """Sabitleme anahtarı: sıkıştırılsa da değişmesin diye .gz uzantısız dosya adı."""
        name = os.path.basename(path)
        return name[:-3] if name.endswith(".gz") else name

    def is_pinned(self, path):
        return self._key(path) in self._pins()

    def toggle_pin(self, path):
        pins = self._pins()
        k = self._key(path)
        if k in pins:
            pins.discard(k)
            state = False
        else:
            pins.add(k)
            state = True
        self._save_pins(pins)
        if state and path.endswith(".gz"):          # sabitlenen rapor açık halde dursun
            self._decompress(path)
        return state

    # ---------------- listeleme / okuma ----------------
    def list(self, query=""):
        """Raporları yeniden eskiye döner: [{path, title, date, size, compressed, pinned}]"""
        if not os.path.isdir(self.folder):
            return []
        pins = self._pins()
        out = []
        for name in os.listdir(self.folder):
            if not (name.endswith(".md") or name.endswith(".md.gz")):
                continue
            path = os.path.join(self.folder, name)
            try:
                st = os.stat(path)
            except OSError:
                continue
            title = self._title(path, name)
            item = {"path": path, "title": title, "size": st.st_size,
                    "date": datetime.datetime.fromtimestamp(self._stamp(name, st.st_mtime)),
                    "compressed": name.endswith(".gz"), "pinned": self._key(path) in pins}
            out.append(item)
        if query:
            q = query.lower()
            out = [i for i in out if q in i["title"].lower() or q in self.read(i["path"]).lower()]
        out.sort(key=lambda i: i["date"], reverse=True)
        return out

    @staticmethod
    def _stamp(name, fallback):
        m = re.match(r"(\d{4}-\d{2}-\d{2})_(\d{4})", name)
        if m:
            try:
                return datetime.datetime.strptime(m.group(1) + m.group(2), "%Y-%m-%d%H%M").timestamp()
            except ValueError:
                pass
        return fallback

    def _title(self, path, name):
        try:
            for line in self.read(path).splitlines()[:5]:
                if line.startswith("#"):
                    return line.lstrip("# ").strip()[:120]
        except Exception:
            pass
        return re.sub(r"^\d{4}-\d{2}-\d{2}_\d{4}_", "", name).replace(".md.gz", "").replace(".md", "")

    def read(self, path):
        if path.endswith(".gz"):
            with gzip.open(path, "rt", encoding="utf-8") as f:
                return f.read()
        with open(path, encoding="utf-8") as f:
            return f.read()

    def delete(self, path):
        pins = self._pins()
        if self._key(path) in pins:
            pins.discard(self._key(path))
            self._save_pins(pins)
        os.remove(path)

    def total_size(self):
        return sum(i["size"] for i in self.list())

    # ---------------- dışa aktarma (Word / PDF) ----------------
    def export(self, path, fmt):
        """Raporu .docx ya da .pdf olarak dışa aktarır: data/raporlar/disa_aktarilan/ altına, raporla aynı
        adla kaydeder. fmt: 'docx' | 'pdf'. Döner: üretilen dosyanın yolu."""
        from . import report_export
        if fmt not in ("docx", "pdf"):
            raise ValueError(f"Desteklenmeyen biçim: {fmt}")
        md = self.read(path)
        name = os.path.basename(path)
        title = self._title(path, name)
        base = self._key(path)
        base = base[:-3] if base.endswith(".md") else base
        out_dir = os.path.join(self.folder, "disa_aktarilan")
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, f"{base}.{fmt}")
        if fmt == "docx":
            report_export.export_docx(md, out_path, title=title)
        else:
            report_export.export_pdf(md, out_path, title=title)
        return out_path

    # ---------------- yer tasarrufu ----------------
    def _compress(self, path):
        gz = path + ".gz"
        with open(path, "rb") as src, gzip.open(gz, "wb", compresslevel=9) as dst:
            dst.write(src.read())
        os.remove(path)
        return gz

    def _decompress(self, path):
        md = path[:-3]
        with gzip.open(path, "rb") as src, open(md, "wb") as dst:
            dst.write(src.read())
        os.remove(path)
        return md

    def cleanup(self):
        """Eski raporları sıkıştırır, sınırlar aşılırsa en eski sabitlenmemiş raporları siler.
        Döner: {"compressed": n, "deleted": n}"""
        stats = {"compressed": 0, "deleted": 0}
        if not os.path.isdir(self.folder):
            return stats
        cutoff = time.time() - self.cfg["compress_after_days"] * 86400
        for item in self.list():
            if (not item["compressed"] and not item["pinned"]
                    and item["date"].timestamp() < cutoff):
                try:
                    self._compress(item["path"])
                    stats["compressed"] += 1
                except Exception as e:
                    print(f"[RAPOR] sıkıştırılamadı: {e}")
        items = self.list()
        limit_bytes = self.cfg["max_total_mb"] * 1024 * 1024
        total = sum(i["size"] for i in items)
        count = len(items)
        for item in reversed(items):            # en eskiden başla
            if count <= self.cfg["max_count"] and total <= limit_bytes:
                break
            if item["pinned"]:
                continue
            try:
                os.remove(item["path"])
                count -= 1
                total -= item["size"]
                stats["deleted"] += 1
            except Exception as e:
                print(f"[RAPOR] silinemedi: {e}")
        return stats


def human_size(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
