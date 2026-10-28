# Core: MK-Agentic-System · Powered by FENIX Engine · (c) 2026 Mustafa Koç · All rights reserved
"""Akıl ve Hafıza: SQLite (ham geçmiş) + ChromaDB (semantik arama, Gemini
embedding ile - bulutta, RAM dostu). Ayrıca günlük özet için kayıt sorgulama."""
import os
import sqlite3
import datetime
import threading

# chromadb ve google.genai AĞIR paketlerdir; yalnızca anlamsal hafıza açıkken (ana uygulama) yüklenir.
# Yan sohbet (v5.10.1) semantic=False ile açar, böylece daha az RAM kullanır.


class _NullCollection:
    """Anlamsal hafıza kapalıyken: yazma yok sayılır, arama boş döner (SQLite geçmişi yine çalışır)."""
    def add(self, *a, **k):
        return None

    def query(self, *a, **k):
        return {"documents": [[]]}


class GeminiEmbeddingFunction:
    def __init__(self, api_key, model_name="gemini-embedding-001", output_dim=768):
        from google import genai as _genai
        self._client = _genai.Client(api_key=api_key)
        self._model = model_name
        self._dim = output_dim

    def __call__(self, input):
        from google.genai import types as _gt
        resp = self._client.models.embed_content(
            model=self._model, contents=list(input),
            config=_gt.EmbedContentConfig(output_dimensionality=self._dim),
        )
        return [e.values for e in resp.embeddings]

    def name(self):
        return f"gemini-{self._model}-{self._dim}d"


class _Rows:
    """Sorgu sonucunu kilit altında tamamen okunmuş halde tutar (cursor thread'ler arası paylaşılmasın)."""
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def __iter__(self):
        return iter(self._rows)


class _LockedConn:
    """SQLite bağlantısını thread'ler arasında güvenle paylaşmak için kilitli sarmalayıcı.
    Arayüz, worker thread'leri ve istatistik thread'i aynı veritabanına yazıyor."""
    def __init__(self, path):
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._lock = threading.RLock()

    def execute(self, sql, params=()):
        with self._lock:
            cur = self._conn.execute(sql, params)
            rows = cur.fetchall() if cur.description else []
        return _Rows(rows)

    def insert(self, sql, params=()):
        """INSERT çalıştırır ve yeni satırın id'sini döner."""
        with self._lock:
            cur = self._conn.execute(sql, params)
            self._conn.commit()
            return cur.lastrowid

    def commit(self):
        with self._lock:
            self._conn.commit()


class Memory:
    def __init__(self, db_path="data/fenix_memory.db", chroma_path="data/chroma_db", gemini_api_key=None,
                 cross_chat=True, semantic=True):
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        self.conn = _LockedConn(db_path)
        self.current_session_id = None      # arayüzde açık olan sohbet
        # False: her sohbet kendi geçmişini kullanır (diğer sohbetlerin konuşmaları bağlama girmez).
        #        "not al" ile alınan notlar her sohbette hatırlanır.
        # True : anlamca ilgili kayıtlar tüm sohbetlerden aranır.
        self.cross_chat = bool(cross_chat)
        # Gizli sohbet: hiçbir şey veritabanına/anlamsal hafızaya yazılmaz, sadece bellekte tutulur
        self.incognito = False
        self._incognito_msgs = []
        self._init_db()
        self.semantic = bool(semantic)
        if not self.semantic:
            self.chroma = None
            self.embed_fn = None
            self.collection = _NullCollection()
            return
        import chromadb
        from chromadb.utils import embedding_functions
        self.chroma = chromadb.PersistentClient(path=chroma_path)
        if gemini_api_key:
            try:
                self.embed_fn = GeminiEmbeddingFunction(api_key=gemini_api_key)
            except Exception as e:
                print(f"[HAFIZA UYARI] Gemini embedding başlatılamadı: {e}")
                self.embed_fn = embedding_functions.DefaultEmbeddingFunction()
        else:
            self.embed_fn = embedding_functions.DefaultEmbeddingFunction()
        self.collection = self.chroma.get_or_create_collection(
            name="fenix_memories", embedding_function=self.embed_fn
        )

    def _init_db(self):
        self.conn.execute("""CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT, role TEXT, content TEXT, mode TEXT)""")
        self.conn.execute("""CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT, kind TEXT, detail TEXT)""")
        # Notlar: kullanıcı notları ('user'), otomatik olay notları ('auto'), gün özetleri ('summary')
        self.conn.execute("""CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT, source TEXT, content TEXT)""")

        # Sohbet oturumları (sol paneldeki sohbet listesi)
        self.conn.execute("""CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, created TEXT, updated TEXT, mode TEXT,
            auto_titled INTEGER DEFAULT 0)""")

        # GÖÇ: eski sürümlerde oluşmuş tablolarda yeni sütunlar yok.
        # CREATE TABLE IF NOT EXISTS mevcut tabloyu değiştirmez, bu yüzden eksikse ekliyoruz.
        def cols(table):
            return [r[1] for r in self.conn.execute(f"PRAGMA table_info({table})").fetchall()]
        if "mode" not in cols("conversations"):
            self.conn.execute("ALTER TABLE conversations ADD COLUMN mode TEXT DEFAULT 'normal'")
        for table in ("conversations", "notes", "events"):
            if "session_id" not in cols(table):
                self.conn.execute(f"ALTER TABLE {table} ADD COLUMN session_id INTEGER")
        self.conn.commit()
        self._migrate_old_messages()

    def _migrate_old_messages(self):
        """Oturum sistemi öncesi mesajları gün gün 'Önceki konuşmalar' sohbetlerine toplar (bir kez)."""
        days = [r[0] for r in self.conn.execute(
            "SELECT DISTINCT substr(timestamp,1,10) FROM conversations WHERE session_id IS NULL").fetchall() if r[0]]
        for day in sorted(days):
            rng = self.conn.execute("SELECT MIN(timestamp), MAX(timestamp) FROM conversations "
                                    "WHERE session_id IS NULL AND timestamp LIKE ?", (f"{day}%",)).fetchone()
            try:
                label = datetime.date.fromisoformat(day).strftime("%d.%m.%Y")
            except ValueError:
                label = day
            sid = self.conn.insert("INSERT INTO sessions (title, created, updated, mode, auto_titled) "
                                   "VALUES (?,?,?,?,1)", (f"Önceki konuşmalar • {label}", rng[0], rng[1], "normal"))
            self.conn.execute("UPDATE conversations SET session_id=? WHERE session_id IS NULL AND timestamp LIKE ?",
                              (sid, f"{day}%"))
        if days:
            self.conn.commit()

    # ---------------- SOHBET OTURUMLARI ----------------
    def create_session(self, mode="normal", title="Yeni sohbet"):
        now = datetime.datetime.now().isoformat()
        return self.conn.insert("INSERT INTO sessions (title, created, updated, mode, auto_titled) VALUES (?,?,?,?,0)",
                                (title, now, now, mode))

    def list_sessions(self, limit=300, query=""):
        """Sohbetleri son güncellenmeye göre döner: [{id, title, created, updated, count}]"""
        sql = ("SELECT s.id, s.title, s.created, s.updated, s.auto_titled, "
               "(SELECT COUNT(*) FROM conversations c WHERE c.session_id = s.id) FROM sessions s ")
        params = []
        if query:
            sql += ("WHERE s.title LIKE ? OR s.id IN (SELECT session_id FROM conversations WHERE content LIKE ?) ")
            params += [f"%{query}%", f"%{query}%"]
        sql += "ORDER BY s.updated DESC LIMIT ?"
        params.append(limit)
        return [{"id": r[0], "title": r[1], "created": r[2], "updated": r[3], "auto_titled": bool(r[4]),
                 "count": r[5]} for r in self.conn.execute(sql, tuple(params)).fetchall()]

    def get_session(self, session_id):
        r = self.conn.execute("SELECT id, title, created, updated, auto_titled FROM sessions WHERE id=?",
                              (session_id,)).fetchone()
        # auto_titled: 0 = henüz başlık yok, 1 = FENIX verdi, 2 = kullanıcı elle verdi
        return {"id": r[0], "title": r[1], "created": r[2], "updated": r[3], "auto_titled": int(r[4] or 0)} if r else None

    def rename_session(self, session_id, title, auto=False):
        title = (title or "").strip()[:80] or "Adsız sohbet"
        self.conn.execute("UPDATE sessions SET title=?, auto_titled=? WHERE id=?", (title, 1 if auto else 2, session_id))
        self.conn.commit()

    def delete_session(self, session_id):
        self.conn.execute("DELETE FROM conversations WHERE session_id=?", (session_id,))
        self.conn.execute("DELETE FROM sessions WHERE id=?", (session_id,))
        self.conn.commit()
        try:
            self.collection.delete(where={"session_id": int(session_id)})
        except Exception:
            pass

    def get_session_messages(self, session_id, limit=400):
        rows = self.conn.execute("SELECT timestamp, role, content FROM conversations WHERE session_id=? "
                                 "ORDER BY id DESC LIMIT ?", (session_id, limit)).fetchall()
        return list(reversed(rows))

    def get_sessions_for_day(self, day):
        """O gün mesajlaşılan sohbetler: [{id, title, first, last, messages:[(ts, role, content)]}]"""
        rows = self.conn.execute(
            "SELECT c.session_id, s.title, c.timestamp, c.role, c.content FROM conversations c "
            "LEFT JOIN sessions s ON s.id = c.session_id WHERE c.timestamp LIKE ? ORDER BY c.id", (f"{day}%",)).fetchall()
        out = {}
        for sid, title, ts, role, content in rows:
            g = out.setdefault(sid, {"id": sid, "title": title or "Sohbet", "first": ts, "last": ts, "messages": []})
            g["last"] = ts
            g["messages"].append((ts, role, content))
        return sorted(out.values(), key=lambda g: g["first"])

    def add_message(self, role, content, mode="normal", session_id=None):
        if not content:
            return
        if self.incognito and session_id is None:
            self._incognito_msgs.append((role, content))
            self._incognito_msgs = self._incognito_msgs[-40:]
            return
        sid = session_id if session_id is not None else self.current_session_id
        ts = datetime.datetime.now().isoformat()
        self.conn.execute("INSERT INTO conversations (timestamp, role, content, mode, session_id) VALUES (?,?,?,?,?)",
                          (ts, role, content, mode, sid))
        if sid is not None:
            self.conn.execute("UPDATE sessions SET updated=? WHERE id=?", (ts, sid))
        self.conn.commit()
        try:
            meta = {"role": role, "timestamp": ts, "mode": mode}
            if sid is not None:
                meta["session_id"] = int(sid)
            self.collection.add(documents=[content], ids=[f"{role}_{ts}"], metadatas=[meta])
        except Exception as e:
            print(f"[HAFIZA UYARI] Chroma kaydı başarısız: {e}")

    def set_incognito(self, on):
        self.incognito = bool(on)
        self._incognito_msgs = []

    # ---------------- UNUTMA ----------------
    def count_matching(self, text):
        like = f"%{text}%"
        n_msgs = self.conn.execute("SELECT COUNT(*) FROM conversations WHERE content LIKE ?", (like,)).fetchone()[0]
        n_notes = self.conn.execute("SELECT COUNT(*) FROM notes WHERE content LIKE ?", (like,)).fetchone()[0]
        return n_msgs, n_notes

    def forget_matching(self, text):
        """İçinde metin geçen konuşma/not kayıtlarını SQLite ve anlamsal hafızadan siler."""
        like = f"%{text}%"
        self.conn.execute("DELETE FROM conversations WHERE content LIKE ?", (like,))
        self.conn.execute("DELETE FROM notes WHERE content LIKE ?", (like,))
        self.conn.commit()
        try:
            self.collection.delete(where_document={"$contains": text})
        except Exception as e:
            print(f"[HAFIZA] anlamsal kayıt silinemedi: {e}")

    def log_event(self, kind, detail):
        if self.incognito and self.current_session_id is None:
            return                              # gizli sohbette yapılanlar da kaydedilmez
        ts = datetime.datetime.now().isoformat()
        self.conn.execute("INSERT INTO events (timestamp, kind, detail, session_id) VALUES (?,?,?,?)",
                          (ts, kind, detail, self.current_session_id))
        self.conn.commit()

    def get_recent(self, limit=10, session_id="current"):
        """Son mesajlar. Varsayılan: açık sohbetin mesajları (sohbet yoksa boş)."""
        sid = self.current_session_id if session_id == "current" else session_id
        if sid is None:
            return list(self._incognito_msgs[-limit:]) if self.incognito else []
        cur = self.conn.execute("SELECT role, content FROM conversations WHERE session_id=? ORDER BY id DESC LIMIT ?",
                                (sid, limit))
        return list(reversed(cur.fetchall()))

    def search_memory(self, query, n_results=4, session_id="current"):
        """Anlamca ilgili kayıtlar. Sohbetlere özel modda yalnızca bu sohbetin mesajları + kullanıcı notları."""
        sid = self.current_session_id if session_id == "current" else session_id
        where = None
        if not self.cross_chat:
            where = ({"$or": [{"session_id": int(sid)}, {"role": "note"}]} if sid is not None
                     else {"role": "note"})
        try:
            if where is None:
                res = self.collection.query(query_texts=[query], n_results=n_results)
            else:
                res = self.collection.query(query_texts=[query], n_results=n_results, where=where)
            return res.get("documents", [[]])[0]
        except Exception:
            return []

    def get_context(self, query, recent_limit=6, semantic_limit=4, item_chars=400):
        """Bağlam = bu sohbetin son mesajları + anlamca ilgili kayıtlar (sohbete özel modda yalnızca bu
        sohbetten ve notlardan; cross_chat açıksa tüm sohbetlerden)."""
        def cut(t):
            t = " ".join((t or "").split())
            return t if len(t) <= item_chars else t[:item_chars] + "…"
        recent = [cut(f"{r}: {c}") for r, c in self.get_recent(recent_limit)]
        semantic = [cut(x) for x in self.search_memory(query, semantic_limit)]
        out, seen = [], set()
        for t in recent + semantic:
            if t and t not in seen:
                seen.add(t)
                out.append(t)
        text = "\n".join(out)
        return text

    # ---------------- NOTLAR ----------------
    def add_note(self, content, source="user"):
        """Geçmişe not ekler. source: 'user' (kullanıcı), 'auto' (otomatik), 'summary' (gün özeti), 'error' (hata kaydı).
        Notlar ayrıca semantik hafızaya da yazılır, böylece 'ne not almıştık?' diye sorulabilir."""
        content = (content or "").strip()
        if not content:
            return
        ts = datetime.datetime.now().isoformat()
        self.conn.execute("INSERT INTO notes (timestamp, source, content, session_id) VALUES (?,?,?,?)",
                          (ts, source, content, self.current_session_id))
        self.conn.commit()
        if source not in ("auto", "error"):
            # Semantik kayıt Gemini embedding (ağ çağrısı) gerektirir: arka planda yap,
            # not veritabanına zaten yazıldı ve çağıran beklemeden döner.
            def _index():
                try:
                    self.collection.add(documents=[f"[Not] {content}"], ids=[f"note_{ts}"],
                                        metadatas=[{"role": "note", "timestamp": ts, "mode": source}])
                except Exception as e:
                    print(f"[HAFIZA UYARI] Not semantik hafızaya yazılamadı: {e}")
            threading.Thread(target=_index, daemon=True).start()

    def log_error(self, where, detail):
        """Hata ayrıntısını Geçmiş'e not düşer ve data/hatalar.log dosyasına ekler (kullanıcıya okunmaz)."""
        detail = (str(detail) or "").strip()[:1500]
        self.add_note(f"{where}: {detail}", source="error")
        try:
            os.makedirs("data", exist_ok=True)
            path = os.path.join("data", "hatalar.log")
            with open(path, "a", encoding="utf-8") as f:
                f.write(f"[{datetime.datetime.now().isoformat(timespec='seconds')}] {where}: {detail}\n")
            from .killswitch import trim_log
            trim_log(path)
        except Exception:
            pass

    def get_days(self, limit=60, session_id=None):
        """Kaydı olan günleri (yeniden eskiye) döner. session_id verilirse sadece o sohbetin günleri."""
        days = set()
        for table in ("conversations", "notes", "events"):
            conds, params = [], []
            if table == "events":
                conds.append("kind != 'activity'")
            if session_id is not None:
                conds.append("session_id = ?")
                params.append(session_id)
            rows = self.conn.execute(
                f"SELECT DISTINCT substr(timestamp,1,10) FROM {table} "
                + (("WHERE " + " AND ".join(conds)) if conds else ""), tuple(params)).fetchall()
            days.update(r[0] for r in rows if r[0])
        if session_id is None or not days:
            days.add(datetime.date.today().isoformat())
        return sorted(days, reverse=True)[:limit]

    def get_activity_summary(self, day=None, sample_seconds=15):
        """Gün içi ekran kategorisi dağılımını dakika olarak döner (StatsTracker kayıtlarından)."""
        day = day or datetime.date.today().isoformat()
        rows = self.conn.execute(
            "SELECT detail FROM events WHERE kind='activity' AND timestamp LIKE ?", (f"{day}%",)
        ).fetchall()
        totals = {}
        for (detail,) in rows:
            cat = (detail or "diğer").split("|", 1)[0]
            totals[cat] = totals.get(cat, 0) + sample_seconds
        return {c: round(s / 60, 1) for c, s in sorted(totals.items(), key=lambda x: -x[1])}

    def get_day_events(self, day=None, session_id=None):
        """Belirli bir günün (varsayılan bugün) konuşmalarını, olaylarını ve notlarını döner.
        'activity' kayıtları (15 sn'de bir örnekleme) olay listesine dahil edilmez; özet olarak
        get_activity_summary ile alınır."""
        day = day or datetime.date.today().isoformat()
        sq, sp = ("", ()) if session_id is None else (" AND session_id = ?", (session_id,))
        conv = self.conn.execute(
            "SELECT timestamp, role, content FROM conversations WHERE timestamp LIKE ?" + sq + " ORDER BY id",
            (f"{day}%",) + sp).fetchall()
        sessions = self.get_sessions_for_day(day)
        if session_id is not None:
            sessions = [g for g in sessions if g["id"] == session_id]
        ev = self.conn.execute(
            "SELECT timestamp, kind, detail FROM events WHERE kind != 'activity' AND timestamp LIKE ?" + sq +
            " ORDER BY id", (f"{day}%",) + sp).fetchall()
        notes = self.conn.execute(
            "SELECT timestamp, source, content FROM notes WHERE timestamp LIKE ?" + sq + " ORDER BY id",
            (f"{day}%",) + sp).fetchall()
        return {"date": day, "conversations": conv, "events": ev, "notes": notes, "sessions": sessions}
