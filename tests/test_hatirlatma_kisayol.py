# Core: MK-Agentic-System · Powered by FENIX Engine · (c) 2026 Mustafa Koç · All rights reserved
"""Hatırlatıcı zaman ifadeleri ve kısayol komutları."""
import datetime

import pytest

from modules import macros
from modules.reminders import parse_when

SIMDI = datetime.datetime(2026, 11, 2, 12, 0)      # Pazartesi 12:00


@pytest.mark.parametrize("ifade, beklenen", [
    ("20 dakika sonra", datetime.datetime(2026, 11, 2, 12, 20)),
    ("1 saat 15 dakika sonra", datetime.datetime(2026, 11, 2, 13, 15)),
    ("yarım saat sonra", datetime.datetime(2026, 11, 2, 12, 30)),
    ("yarın 9:00", datetime.datetime(2026, 11, 3, 9, 0)),
    ("bugün akşam 8", datetime.datetime(2026, 11, 2, 20, 0)),
    ("cuma 14:00", datetime.datetime(2026, 11, 6, 14, 0)),
    ("15:30", datetime.datetime(2026, 11, 2, 15, 30)),
    ("10:00", datetime.datetime(2026, 11, 3, 10, 0)),          # geçmiş saat -> ertesi gün
    ("öbür gün 10", datetime.datetime(2026, 11, 4, 10, 0)),
    ("saat 3'te", datetime.datetime(2026, 11, 2, 15, 0)),       # öğleden sonra kabul edilir
    ("2026-12-01 10:00", datetime.datetime(2026, 12, 1, 10, 0)),
])
def test_zaman_ifadeleri(ifade, beklenen):
    assert parse_when(ifade, SIMDI) == beklenen


@pytest.mark.parametrize("ifade", ["bilmem ne zaman", "", "yakında"])
def test_anlasilmayan_zaman_none_doner(ifade):
    assert parse_when(ifade, SIMDI) is None


def test_hatirlatma_kaydedilir_ve_zamani_gelince_gorunur():
    from modules.memory import Memory
    from modules.reminders import ReminderStore
    m = Memory(db_path="data/test.db", semantic=False)
    st = ReminderStore(m.conn)
    st.add(SIMDI + datetime.timedelta(minutes=5), "çayı kapat")
    assert st.due_now(SIMDI) == []
    gelen = st.due_now(SIMDI + datetime.timedelta(minutes=6))
    assert [r["text"] for r in gelen] == ["çayı kapat"]
    st.mark_done(gelen[0]["id"])
    assert st.pending() == []


def test_kisayol_kaydet_calistir_sil():
    macros.save("çalışma modu", ["VS Code'u aç", "Spotify'ı aç"])
    for cumle in ("çalışma modu", "çalışma modunu aç", "Çalışma modunu başlat lütfen"):
        assert macros.match(cumle) == ("çalışma modu", ["VS Code'u aç", "Spotify'ı aç"]), cumle
    assert macros.match("çalışma modu kısayolunu değiştir ve müziği kapat") is None
    assert macros.delete("çalışma modu")
    assert macros.match("çalışma modu") is None


def test_bos_kisayol_kaydedilmez():
    with pytest.raises(ValueError):
        macros.save("boş", [])
