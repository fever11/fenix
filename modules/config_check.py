# Core: MK-Agentic-System · Powered by FENIX Engine · (c) 2026 Mustafa Koç · GPL-3.0-only (LICENSE, NOTICE.md)
"""Ayar dosyası kontrolü / settings file check.
Paylaşılan pakette config.yaml YOKTUR (API anahtarları paylaşılmasın diye). Yeni kurulumda config.example.yaml'dan
anahtarsız bir config.yaml oluşturulur ve kullanıcı kendi anahtarını girer.
The shared package never contains config.yaml; it is created from config.example.yaml on first run."""
import os
import shutil

EXAMPLE = "config.example.yaml"


def ensure_config(path="config.yaml", example=EXAMPLE):
    """-> 'var' (config.yaml zaten var) | 'olusturuldu' (örnekten kopyalandı) | 'yok' (ne config ne örnek var)"""
    if os.path.exists(path):
        return "var"
    if os.path.exists(example):
        shutil.copyfile(example, path)
        return "olusturuldu"
    return "yok"
