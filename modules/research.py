# Core: MK-Agentic-System · Powered by FENIX Engine · (c) 2026 Mustafa Koç · GPL-3.0-only (LICENSE, NOTICE.md)
"""
Derin Araştırma Motoru (Devil Mod)
----------------------------------
Modelin "ne kadar araştırayım" kararına bırakılmaz; adımlar kodda sabittir:

  1. Plan        : soru alt sorulara ve 4-6 arama sorgusuna bölünür
  2. Arama       : her sorgu web'de aranır, kaynaklar çeşitlendirilir (site başına en fazla 2)
  3. Okuma       : sayfalar TARAYICI AÇMADAN, paralel olarak arka planda çekilir
  4. Not çıkarma : her sayfadan soruyla ilgili somut bilgiler kaynak numarasıyla çıkarılır
  5. Eksik kontrol: notlar yeterli mi? değilse yeni sorgularla 2. tur (ve gerekirse 3.)
  6. Rapor       : kaynaklı, bölümlü Markdown rapor yazılır ve data/raporlar/ altına kaydedilir

Site denetimi (URL + analiz isteği) için arama yerine sitenin kendi sayfaları taranır.

Her adım arasında iptal kontrolü yapılır (arayüzdeki "Görevi durdur").
Bekleme süresi yapay değildir; süre gerçekten yapılan iş kadardır.
"""
import os
import re
import json
import datetime
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse

from . import web_analyzer as wa
from . import functions as fx
from . import audit_rules as AR


URL_RE = re.compile(r"(https?://[^\s)\]]+|\b(?:www\.)?[\w\-]+\.(?:com|net|org|io|dev|tr|gov|edu|co|ai|app)"
                    r"(?:\.tr)?(?:/[^\s)\]]*)?)", re.IGNORECASE)

SKIP_DOMAINS = ("youtube.com", "youtu.be", "facebook.com", "instagram.com", "tiktok.com",
                "twitter.com", "x.com", "pinterest.", "linkedin.com")

DEFAULTS = {
    "max_pages": 12,          # 1. turda okunacak en fazla sayfa
    "extra_pages": 6,         # sonraki her turda eklenecek en fazla sayfa
    "rounds": 3,              # en fazla tur (1 = sadece ilk tur)
    "parallel_fetch": 4,      # aynı anda çekilen sayfa
    "page_chars": 5000,       # sayfa başına modele verilen metin
    "fast_model": "openai/gpt-oss-20b",
    "site_max_pages": 8,
}


class Cancelled(Exception):
    pass


def _parse_json(text):
    """Model cevabındaki ilk JSON nesnesini güvenle ayıklar."""
    if not text:
        return {}
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return {}
    try:
        return json.loads(m.group(0))
    except Exception:
        return {}


def _slug(text, n=40):
    tr = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")
    s = re.sub(r"[^a-zA-Z0-9]+", "-", text.translate(tr)).strip("-").lower()
    return s[:n] or "rapor"


class DeepResearch:
    def __init__(self, llm, cfg=None, on_stage=None, on_plan=None, notify=None, cancelled=None,
                 report_dir="data/raporlar"):
        self.llm = llm
        self.cfg = dict(DEFAULTS, **(cfg or {}))
        self.on_stage = on_stage or (lambda s: None)
        self.on_plan = on_plan or (lambda s: None)
        self.notify = notify or (lambda t: None)
        self.cancelled = cancelled or (lambda: False)
        self.report_dir = report_dir

    # ---------------- yardımcılar ----------------
    def _check(self):
        if self.cancelled():
            raise Cancelled()

    def _stage(self, name):
        self._check()
        self.on_stage(name)

    def _ask(self, mode_cfg, prompt, fast=False, system=None):
        self._check()
        return self.llm.complete(mode_cfg, prompt, system=system, fast=fast,
                                 fast_model=self.cfg["fast_model"])

    def _search(self, queries, seen_urls, limit):
        """Sorguları arar; sonuçları sorgular arasında sırayla harmanlayarak çeşitli kaynak seçer."""
        per_query = []
        with ThreadPoolExecutor(max_workers=3) as ex:
            for res in ex.map(fx.search_web, queries):
                per_query.append(res.get("results", []) if res.get("status") == "ok" else [])
        self._check()
        picked, domains = [], {}
        i = 0
        while len(picked) < limit and any(i < len(r) for r in per_query):
            for results in per_query:
                if i < len(results) and len(picked) < limit:
                    item = results[i]
                    url = item.get("url", "")
                    host = urlparse(url).netloc.lower()
                    if (not url.startswith("http") or url in seen_urls or url.lower().endswith(".pdf")
                            or any(d in host for d in SKIP_DOMAINS) or domains.get(host, 0) >= 2):
                        continue
                    seen_urls.add(url)
                    domains[host] = domains.get(host, 0) + 1
                    picked.append(item)
            i += 1
        return picked

    def _fetch_many(self, urls):
        """Sayfaları paralel çeker (tarayıcı açmaz). Okunamayan / boş sayfaları eler."""
        pages, total = [], len(urls)

        def fetch(u):
            if self.cancelled():
                return None
            return wa.fetch_and_parse(u, timeout=15, max_chars=self.cfg["page_chars"])

        with ThreadPoolExecutor(max_workers=self.cfg["parallel_fetch"]) as ex:
            for n, rep in enumerate(ex.map(fetch, urls), 1):
                self._check()
                if not rep or "error" in rep or rep.get("status_code", 500) >= 400 or rep.get("text_length", 0) < 300:
                    self.notify(f"✗ okunamadı ({n}/{total})")
                    continue
                pages.append(rep)
                self.notify(f"✓ {n}/{total} okundu: {rep.get('title', '')[:40]}")
        return pages

    def _extract(self, mode_cfg, question, subqs, pages, start_index):
        """Sayfalardan kaynak numaralı not çıkarır (2'şerli gruplar, hızlı model)."""
        groups = [pages[i:i + 2] for i in range(0, len(pages), 2)]
        notes = [None] * len(groups)

        def work(gi):
            if self.cancelled():
                return gi, ""
            parts = []
            for j, pg in enumerate(groups[gi]):
                num = start_index + gi * 2 + j
                parts.append(f"[{num}] {pg.get('title', '')}\nURL: {pg.get('final_url')}\n{pg.get('text_excerpt', '')}")
            prompt = (f"ARAŞTIRMA SORUSU: {question}\nALT SORULAR: {'; '.join(subqs)}\n\n"
                      "Aşağıdaki sayfalardan bu soruyla İLGİLİ somut bilgileri (sayılar, tarihler, isimler, "
                      "özellikler, karşılaştırmalar, iddialar) kısa maddeler halinde çıkar. Her maddenin sonuna "
                      "kaynak numarasını köşeli parantezle yaz, örn. [3]. Sayfada olmayan bir şeyi ekleme. "
                      "Bir sayfa ilgisizse onun için sadece 'İLGİSİZ [n]' yaz.\n\n" + "\n\n---\n\n".join(parts))
            try:
                return gi, self._ask(mode_cfg, prompt, fast=True)
            except Cancelled:
                return gi, ""
            except Exception as e:
                fx.report_error("araştırma not çıkarma", e)
                return gi, ""

        with ThreadPoolExecutor(max_workers=2) as ex:
            for done, (gi, txt) in enumerate(ex.map(work, range(len(groups))), 1):
                notes[gi] = txt
                self.notify(f"📝 notlar {done}/{len(groups)}")
        self._check()
        return [n for n in notes if n and n.strip()]

    def _save(self, title, text):
        os.makedirs(self.report_dir, exist_ok=True)
        stamp = datetime.datetime.now().strftime("%Y-%m-%d_%H%M")
        path = os.path.join(self.report_dir, f"{stamp}_{_slug(title)}.md")
        from . import imza
        with open(path, "w", encoding="utf-8") as f:
            f.write(imza.sign_report(text))
        return path

    @staticmethod
    def _summary_of(report):
        """Raporun ÖZET bölümünü (seslendirme ve chat için) ayıklar."""
        m = re.search(r"(?:^|\n)#+\s*(?:Kısa\s+)?Özet\s*\n+(.+?)(?:\n#|\Z)", report, re.IGNORECASE | re.DOTALL)
        if m:
            return m.group(1).strip()
        paras = [p.strip() for p in report.split("\n\n") if p.strip() and not p.strip().startswith("#")]
        return paras[0] if paras else report[:600]

    def _sources_md(self, sources):
        return "\n".join(f"[{i}] {s.get('title', '')} — {s.get('final_url', '')}" for i, s in enumerate(sources, 1))

    # ---------------- GENEL DERİN ARAŞTIRMA ----------------
    @staticmethod
    def _norm(t):
        return (t or "").lower().translate(str.maketrans("çğıöşü", "cgiosu"))

    def _direct_pages(self, urls, question, subqs, seen):
        """Kullanıcının/bağlamın işaret ettiği siteleri doğrudan okur ve soruyla ilgili alt sayfalarına iner
        (arama motoru sonuç vermese bile çalışır). Alt alan adındaki bölüm/birim sitelerine geçerse
        oranın da ilgili sayfalarına bir kat daha iner (ör. universite.edu.tr -> bolum.universite.edu.tr -> müfredat)."""
        roots = self._fetch_many(urls[:3])
        domain_words = set()
        for r in roots:
            domain_words |= set(re.findall(r"[a-z0-9]{4,}", self._norm(wa.registered_domain(urlparse(r["final_url"]).netloc))))
        words = {w for w in re.findall(r"[a-z0-9]{4,}", self._norm(question + " " + " ".join(subqs)))}
        words -= domain_words      # site adı her linkte geçer, puanı şişirmesin
        words -= {"nedir", "neler", "nasil", "hakkinda", "bilgi", "olan", "icin", "gibi", "yapabilir", "yazar"}
        words |= {"kultur", "culture", "kariyer", "career", "hakkimizda", "about", "ekip", "team", "benefit",
                  "yan-hak", "is-ilan", "jobs", "deger", "values"} if any(
            k in self._norm(question) for k in ("kultur", "calisan", "ayricalik", "kariyer", "sirket")) else set()
        words |= {"mufredat", "ders", "akademik", "kadro", "ogretim", "personel", "staj", "program", "hakkinda",
                  "duyuru", "kulup", "mezun"} if any(
            k in self._norm(question) for k in ("bolum", "universite", "fakulte", "okul", "program")) else set()

        def pick(pages, limit):
            cands = []
            for r in pages:
                seen.add(r["final_url"])
                page_host = urlparse(r["final_url"]).netloc
                labels = r.get("link_labels", [])
                for li, link in enumerate(r.get("links", [])):
                    if link in seen:
                        continue
                    u = urlparse(link)
                    # aynı sitedeki linklerde alan adını sayma (her linkte geçer); başka alt siteye
                    # giden linkte alan adı anlamlı (bilgisayar.universite.edu.tr)
                    where = u.path + ("" if u.netloc == page_host else " " + u.netloc)
                    hay = self._norm(where + " " + (labels[li] if li < len(labels) else ""))
                    score = sum(1 for w in words if w in hay)
                    if score:
                        cands.append((score, link))
            cands.sort(key=lambda x: -x[0])
            out = []
            for _, link in cands:
                if link not in seen and len(out) < limit:
                    seen.add(link)
                    out.append(link)
            return out

        subs = self._fetch_many(pick(roots, 6)) if roots else []
        root_hosts = {urlparse(r["final_url"]).netloc for r in roots}
        other_sites = [p for p in subs if urlparse(p["final_url"]).netloc not in root_hosts]
        deeper = self._fetch_many(pick(other_sites, 5)) if other_sites else []
        if deeper:
            self.notify(f"↳ alt siteden {len(deeper)} sayfa daha okundu")
        return roots + subs + deeper

    def run(self, question, mode_cfg, context=""):
        rounds = max(1, int(self.cfg["rounds"]))
        steps = ["Plan çıkarılıyor", "Kaynaklar aranıyor", "Sayfalar okunuyor", "Notlar çıkarılıyor",
                 "Eksikler kontrol ediliyor", "Ek araştırma", "Rapor yazılıyor", "Rapor kaydediliyor"]
        self.on_plan(steps)
        started = datetime.datetime.now()

        # 1) Plan (+ konu türü: rapor başlıkları türe göre seçilir)
        self._stage("Plan çıkarılıyor")
        ctx = f"[Önceki konuşmadan bağlam — 'site', 'şirket', 'bunu' gibi ifadeler buna atıf olabilir]\n{context[:3000]}\n\n" if context else ""
        plan = _parse_json(self._ask(mode_cfg, (
            f"{ctx}Kullanıcının araştırma isteği: {question}\n\n"
            "Bunu derinlemesine araştırmak için bir plan çıkar. İstek belirli bir siteye/şirkete atıf yapıyorsa "
            "(bağlamdan da olabilir) onun adını sorgulara açıkça yaz ve adresini dogrudan_adresler'e ekle. "
            "Konunun türünü şunlardan seç: kurum (üniversite/bölüm/okul/kamu kurumu), kisi_hesap (kişi ya da sosyal "
            "medya hesabı), yazilim_sistem (yazılım, uygulama, bilgi sistemi), urun (ürün/hizmet), karsilastirma, "
            "sirket, guncel (olay/haber), konu (genel). Alt soruları bu türe uygun seç.\n"
            "SADECE şu JSON'u döndür:\n"
            '{"baslik": "kısa rapor başlığı", "tur": "yukarıdakilerden biri", "alt_sorular": ["3-6 alt soru"], '
            '"sorgular": ["4-6 farklı web arama sorgusu; gerekiyorsa bazıları İngilizce olsun"], '
            '"dogrudan_adresler": ["doğrudan okunması gereken site adresleri, yoksa boş"]}'), fast=True))
        title = (plan.get("baslik") or question)[:80]
        kind = AR.research_type(plan.get("tur"), question)
        kind_label, kind_sections, kind_rule = AR.RESEARCH_TYPES[kind]
        subqs = [q for q in plan.get("alt_sorular", []) if isinstance(q, str)][:6] or [question]
        queries = [q for q in plan.get("sorgular", []) if isinstance(q, str)][:6] or [question]
        walled_m = AR.WALLED_RE.search(question)
        walled = walled_m.group(1).lower() if walled_m else ""
        self.notify(f"Konu türü: {kind_label} • Plan: " + " | ".join(subqs[:4]))

        direct = [u for u in plan.get("dogrudan_adresler", []) if isinstance(u, str) and "." in u]
        for m in URL_RE.finditer(question):
            direct.append(m.group(0))
        direct = list(dict.fromkeys(u if u.startswith("http") else "https://" + u for u in direct))[:3]
        direct = [u for u in direct if not any(d in urlparse(u).netloc.lower() for d in SKIP_DOMAINS)]

        # 2) Arama
        self._stage("Kaynaklar aranıyor")
        seen = set()
        picked = self._search(queries, seen, self.cfg["max_pages"])
        self.notify(f"{len(picked)} arama sonucu seçildi" + (f", {len(direct)} doğrudan adres" if direct else ""))

        # 3) Okuma (önce doğrudan adresler ve ilgili alt sayfaları, sonra arama sonuçları)
        self._stage("Sayfalar okunuyor")
        sources = self._direct_pages(direct, question, subqs, seen) if direct else []
        if picked:
            sources += self._fetch_many([p["url"] for p in picked])
        if not sources:
            if walled:
                return {"text": AR.weak_result_text(question, 0, 0, [], walled, bool(direct), kind),
                        "speak": f"{walled.capitalize()} içeriğini okuyamıyorum."}
            return {"text": "Araştırma için kaynak bulamadım: arama motorları sonuç vermedi ve okunabilecek "
                            "bir adres de yoktu. Ayrıntı Geçmiş'teki hata notunda. Siteyi adresiyle yazarsan "
                            "(ör. ornek.com) doğrudan oradan araştırırım.",
                    "speak": "Araştırma için kaynak bulamadım."}

        # 4) Not çıkarma
        self._stage("Notlar çıkarılıyor")
        notes = self._extract(mode_cfg, question, subqs, sources, 1) if sources else []

        # 5-6) Eksik kontrolü + ek turlar
        self._stage("Eksikler kontrol ediliyor")
        extra_round = 1
        while extra_round < rounds:
            gap = _parse_json(self._ask(mode_cfg, (
                f"ARAŞTIRMA SORUSU: {question}\nALT SORULAR: {'; '.join(subqs)}\n\nŞU ANA KADARKİ NOTLAR:\n"
                + "\n".join(notes)[:12000] +
                "\n\nNotlar soruyu ve alt soruları tatmin edici şekilde cevaplıyor mu? SADECE şu JSON'u döndür:\n"
                '{"yeterli": true/false, "eksikler": ["..."], "sorgular": ["en fazla 3 yeni arama sorgusu"]}')))
            if gap.get("yeterli", True) or not gap.get("sorgular"):
                break
            self._stage("Ek araştırma")
            self.notify("Eksik: " + "; ".join(gap.get("eksikler", [])[:3]))
            more = self._search([q for q in gap["sorgular"] if isinstance(q, str)][:3], seen, self.cfg["extra_pages"])
            new_pages = self._fetch_many([p["url"] for p in more]) if more else []
            if new_pages:
                notes += self._extract(mode_cfg, question, subqs, new_pages, len(sources) + 1)
                sources += new_pages
            extra_round += 1
            if not new_pages:
                break

        # v5.8: ilgisiz kaynakları ele, numaraları baştan sırala
        clean_notes, mapping, facts = AR.relevant_sources(notes, len(sources))
        used_sources = [sources[old - 1] for old in sorted(mapping)]
        fact_lines = [x for x in clean_notes if re.search(r"\[\d", x)]
        self.notify(f"{len(sources)} sayfadan {len(used_sources)} tanesi konuyla ilgili • {facts} bilgi")

        # Alt soruların hangileri gerçekten cevaplanabildi? (boş başlık yazılmasın)
        answered, missing = list(range(1, len(subqs) + 1)), []
        if fact_lines:
            cov = _parse_json(self._ask(mode_cfg, (
                "ALT SORULAR:\n" + "\n".join(f"{k}. {q}" for k, q in enumerate(subqs, 1)) +
                "\n\nNOTLAR:\n" + "\n".join(fact_lines)[:10000] +
                "\n\nHer alt soru için notlarda somut bir cevap var mı? SADECE JSON döndür: "
                '{"cevaplanan": [numaralar], "bulunamayan": [numaralar]}'), fast=True))
            if isinstance(cov.get("cevaplanan"), list):
                answered = [k for k in cov["cevaplanan"] if isinstance(k, int) and 1 <= k <= len(subqs)]
                missing = [k for k in range(1, len(subqs) + 1) if k not in answered]

        # Bilgi yetersizse: rapor yazma, durumu ve yapılabilecekleri söyle
        if facts < 3 or not used_sources or not answered:
            self.notify("Bilgi yetersiz: rapor yazılmadı")
            text = AR.weak_result_text(question, len(sources), len(used_sources), fact_lines, walled, bool(direct), kind)
            return {"text": text, "speak": text.split("\n")[0]}

        # 7) Rapor (türe özel başlıklar, sadece cevaplanan konular)
        self._stage("Rapor yazılıyor")
        sources_md = self._sources_md(used_sources)
        report = self._ask(mode_cfg, (
            f"ARAŞTIRMA SORUSU: {question}\nKONU TÜRÜ: {kind_label}\n"
            f"CEVAPLANAN ALT SORULAR: {'; '.join(subqs[k - 1] for k in answered)}\n"
            f"BULUNAMAYAN ALT SORULAR: {'; '.join(subqs[k - 1] for k in missing) or '(yok)'}\n\n"
            f"KAYNAKLAR:\n{sources_md}\n\nTOPLANAN NOTLAR:\n" + "\n".join(clean_notes)[:24000] +
            "\n\nBu notlara dayanarak Türkçe bir araştırma raporu yaz (Markdown). Yapı:\n"
            "# <başlık>\n## Özet\n(3-5 cümle, düz metin: ne bulundu, ne bulunamadı)\n"
            f"Sonra bu türe uygun başlıklardan SADECE notlarda karşılığı olanları kullan: {', '.join(kind_sections)}. "
            "Notlarda karşılığı olmayan başlığı hiç yazma; gerekirse başlıkları birleştir ya da notlara göre yeniden adlandır.\n"
            + ("## Bulunamayanlar\n(bulunamayan alt soruları tek listede, her biri tek satır)\n" if missing else "") +
            "## Sonuç\n(sadece notlardan çıkan değerlendirme; kanıtı olmayan genel öneri yazma)\n\n"
            f"KURALLAR: {kind_rule} Her somut bilgiden sonra kaynak numarası yaz, örn. [2]. Notlarda olmayan bilgiyi "
            "uydurma. Tabloyu sadece en az iki şeyi notlardaki verilerle karşılaştırırken kullan. Emoji ve imza "
            "kullanma. Kaynak listesini yazma, sistem ekleyecek."
            + (f" {walled.capitalize()} giriş istediği için doğrudan okunamadı; bunu özette bir cümleyle belirt." if walled else "")),
            system="Sen kıdemli bir araştırma analistisin. Türkçe, net ve kaynaklı yazarsın; uydurmazsın, "
                   "boş başlık açmazsın.")
        report = AR.sanitize_report(report)

        secs = int((datetime.datetime.now() - started).total_seconds())
        skipped = len(sources) - len(used_sources)
        full = (f"{report}\n\n## Kaynaklar\n{sources_md}\n\n"
                f"---\n_{kind_label} • {len(sources)} sayfa okundu, {len(used_sources)} tanesi kullanıldı"
                + (f" ({skipped} ilgisiz sayfa elendi)" if skipped else "") +
                f" • {len(queries)} ana sorgu • {secs} sn • FENIX Devil mod_\n")

        # 8) Kaydet
        self._stage("Rapor kaydediliyor")
        path = self._save(title, full)
        summary = self._summary_of(report)
        return {"text": f"{summary}\n\n📄 Ayrıntılı rapor ({len(used_sources)} kaynak, {secs} sn) açıldı ve "
                        f"kaydedildi: {path}",
                "speak": summary, "report_title": title, "report": full, "report_path": path}

    # ---------------- SİTE DENETİMİ (çok sayfa) ----------------
    def site_audit(self, url, user_goal, mode_cfg):
        """v5.8: ölçümler ve bulgular KODDA (audit_rules), site türüne göre kontrol listesi; model sadece
        özet, türe özel değerlendirme ve öncelik sırasını yazar. Sayılar ve tablo koddan gelir."""
        steps = ["Ana sayfa çekiliyor", "Güvenlik gözlemleri", "Alt sayfalar taranıyor", "Bulgular çıkarılıyor",
                 "Rapor yazılıyor", "Rapor kaydediliyor"]
        self.on_plan(steps)
        started = datetime.datetime.now()

        self._stage("Ana sayfa çekiliyor")
        root = wa.fetch_and_parse(url, timeout=20, max_chars=self.cfg["page_chars"])
        if "error" in root:
            fx.report_error("site denetimi", root["error"])
            return {"text": "Siteye ulaşamadım, bir hata ile karşılaştım. Ayrıntıyı Geçmiş'e not ettim.",
                    "speak": "Siteye ulaşamadım."}
        self.notify(f"✓ ana sayfa: {root.get('title', '')[:40]}")

        # Pasif güvenlik/durum gözlemleri: TLS/sertifika, DNS/WHOIS, robots/sitemap, teknoloji parmak izi.
        # Herkese açık bilgidir; zafiyet taraması/sızma denemesi yapılmaz (bkz. web_analyzer.security_inspect).
        self._stage("Güvenlik gözlemleri")
        try:
            sec = wa.security_inspect(root["final_url"])
        except Exception as e:
            sec = {"hata": str(e)[:160]}
        self.notify("✓ TLS/DNS/robots gözlemleri tamamlandı")

        self._stage("Alt sayfalar taranıyor")
        links = AR.pick_links(root["final_url"], root.get("links", []), self.cfg["site_max_pages"] - 1)
        fetched = [root] + self._fetch_many(links)
        pages, dups = AR.dedupe_pages(fetched)
        if dups:
            self.notify(f"↺ {len(dups)} adres başka bir sayfayla aynı içeriği veriyor, tek sayfa sayıldı")

        self._stage("Bulgular çıkarılıyor")
        site = AR.classify_site(pages, sec)
        findings, ok_items, not_measured = AR.build_findings(pages, sec if "hata" not in sec else {}, site, dups)
        self.notify(f"Site türü: {site['etiket']} • {len(findings)} bulgu")
        security_md = wa.security_summary_md(sec) if "hata" not in sec else f"- gözlemler alınamadı ({sec['hata']})"

        self._stage("Rapor yazılıyor")
        host = urlparse(root["final_url"]).netloc
        kinds = [site["etiket"]] + site.get("ikincil_etiket", [])
        focus = "\n".join(f"- {AR.SITE_TYPES[k]}: {AR.TYPE_FOCUS[k]}" for k in [site["tur"]] + site.get("ikincil", []))
        flist = "\n".join(f"{x['id']} [{x['seviye']}] {x['alan']}: {x['baslik']} — {x['kanit']}" for x in findings) or "(bulgu yok)"
        excerpts = "\n".join(f"[{i}] {p.get('title', '')[:70]} — {p.get('text_excerpt', '')[:500]}"
                              for i, p in enumerate(pages, 1))
        report = self._ask(mode_cfg, (
            f"Kullanıcının isteği: {user_goal}\nSite: {root['final_url']} ({len(pages)} sayfa tarandı)\n"
            f"Site türü (kodla belirlendi): {', '.join(kinds)} — kanıt: {'; '.join(site['kanit'])}\n\n"
            f"BU TÜR İÇİN ODAK:\n{focus}\n\n"
            f"ÖLÇÜLEN BULGULAR (kodla çıkarıldı, sayılar kesin):\n{flist}\n\n"
            f"İYİ DURUMDA OLANLAR:\n" + "\n".join(f"- {x}" for x in ok_items) + "\n\n"
            f"SAYFA METİNLERİNDEN KESİTLER (sitenin ne yaptığını anlamak için):\n{excerpts[:6000]}\n\n"
            "Bu siteye ÖZEL bir denetim yorumu yaz (Markdown). Yapı:\n"
            f"# <{host} için kısa, siteye özgü başlık>\n"
            "## Özet\n(3-5 cümle: site ne yapıyor, bu türde bir site için genel durum, en önemli 2-3 konu)\n"
            f"## {site['etiket'].capitalize()} olarak değerlendirme\n(ODAK maddelerini bu sitenin gerçek "
            "içeriğiyle ilişkilendir; bulgulara id'leriyle atıf yap, örn. (B3). Sitenin kendi ürün/kurs/sayfa "
            "adlarını kullanarak somut örnek ver; örneğin eksik meta açıklaması için bu sayfaya uygun bir örnek "
            "açıklama yaz.)\n"
            "## Öncelikli Aksiyonlar\n(numaralı, en etkiliden başla; her madde bir ya da birkaç bulguya dayansın, "
            "id'sini yaz; 'nasıl yapılır' kısmı bu sitenin altyapısına göre olsun)\n\n"
            "KURALLAR: Listede olmayan bir sorunu yazma. Yeni sayı, süre ya da yüzde uydurma; sayıları bulgulardan "
            "aynen al. Ölçülmeyen bir şey (Core Web Vitals, görsel formatı, kontrast) hakkında hüküm verme. Bulgu "
            "listesini ve ölçüm tablosunu tekrar yazma, sistem ekleyecek. Tablo, emoji ve imza kullanma. "
            "Saldırı/tarama aracı önerme. Ton yapıcı olsun; amaç site sahibini bilgilendirmek."),
            system="Sen deneyimli bir web denetim uzmanısın. Türkçe, net ve bu siteye özgü yazarsın; ölçülmemiş "
                   "hiçbir şeyi iddia etmezsin.")
        report = AR.sanitize_report(report)

        secs = int((datetime.datetime.now() - started).total_seconds())
        full = (f"{report}\n\n{AR.findings_md(findings, ok_items, not_measured)}\n"
                f"{AR.measurement_table_md(pages)}\n"
                f"## Güvenlik/Durum Gözlemleri (pasif, herkese açık bilgi)\n{security_md}\n\n"
                f"## Taranan Sayfalar\n{self._sources_md(pages)}\n\n"
                f"---\n_Site türü: {', '.join(kinds)} • {len(pages)} sayfa tarandı • {len(findings)} bulgu • {secs} sn • "
                f"FENIX Devil mod. Bu rapor herkese açık, pasif gözlemlere dayanır; site sahibini bilgilendirmek içindir._\n")
        self._stage("Rapor kaydediliyor")
        title = f"Site denetimi {host}"
        path = self._save(title, full)
        summary = self._summary_of(report)
        return {"text": f"{summary}\n\n📄 Denetim raporu ({len(pages)} sayfa, {len(findings)} bulgu, {secs} sn) açıldı ve "
                        f"kaydedildi: {path}",
                "speak": summary, "report_title": title, "report": full, "report_path": path}
