# FENIX Installationsanleitung (Deutsch)

Dauer etwa **15 Minuten**. Keine Vorkenntnisse nötig; folge einfach den Schritten.

## Was du brauchst

| | |
|---|---|
| Computer | Windows 10 oder 11 |
| Programm | Python 3.12 (kostenlos) |
| Schlüssel | Gemini-API-Schlüssel (kostenlos, erforderlich) |
| Optional | Groq-API-Schlüssel (kostenlos; schnellerer Chat, bessere Spracherkennung) |
| Optional | NVIDIA-API-Schlüssel (kostenlos; Reserve-Chat, wenn Groq aufgebraucht ist) — https://build.nvidia.com |

## 1. FENIX herunterladen

1. Auf der GitHub-Seite den grünen Knopf **Code** → **Download ZIP** drücken.
2. ZIP rechts anklicken → **Alle extrahieren**. Den Ordner an einen einfachen Ort legen, z. B. `Dokumente\fenix`.

## 2. Python installieren

1. **Python 3.12** von https://www.python.org/downloads/ herunterladen.
2. Im ersten Installationsfenster **"Add python.exe to PATH" anhaken**, dann **Install Now**.

## 3. Gemini-Schlüssel holen

1. https://aistudio.google.com/apikey öffnen und mit dem Google-Konto anmelden.
2. **Create API key** → Schlüssel kopieren. Den Schlüssel **niemals weitergeben**.
3. (Optional) Einen Groq-Schlüssel gibt es unter https://console.groq.com/keys.

## 4. Installation starten

1. Im FENIX-Ordner doppelt auf **`Setup.bat`** klicken.
   - Bei "Der Computer wurde durch Windows geschützt": **Weitere Informationen → Trotzdem ausführen**.
2. Im Fenster die Sprache wählen (1-6).
3. Fehlt Python, sagt die Installation das und bietet die automatische Installation an.
4. Warten, bis die Pakete installiert sind (5-10 Minuten). Auf dem Desktop erscheint eine **FENIX**-Verknüpfung.

## 5. FENIX starten und Schlüssel einfügen

- Doppelklick auf das **FENIX**-Symbol auf dem Desktop.
- Beim ersten Start erscheint ein kleines Fenster **API-Schlüssel**: Gemini-Schlüssel (und ggf. Groq) einfügen, **Speichern und starten** klicken. Keine Datei bearbeiten nötig.
- Die Sprache lässt sich später unter **⚙️ Einstellungen** ändern.

## Kurze Bedienung

| Was | Wie |
|---|---|
| Textchat | Unten tippen, **Enter** |
| Sprachchat | Knopf **🎤 Push-to-Talk** oder **F9** |
| Datei / Bild anhängen | **📎**, Drag & Drop oder **Strg+V** |
| Modus | **Sicher** (nur Chat) · **Normal** (Alltag, fragt bei Riskantem) · **Devil** (tiefe Recherche, Berichte) |
| Notaus | **Strg+Alt+Q** oder Maus 1,5 s in die obere linke Ecke |

Vor riskanten Aktionen (Löschen, Herunterfahren, Download usw.) **fragt FENIX in jedem Modus nach**.

## Probleme?

| Symptom | Lösung |
|---|---|
| "Python nicht gefunden" | Python neu installieren und **Add python.exe to PATH** anhaken. |
| Schlüsselfehler / keine Antwort | **`Connection_Test.bat`** starten; zeigt den fehlerhaften Schlüssel. |
| Mikrofon wird nicht gehört | **`Microphone_Test.bat`** starten. In den Windows-Soundeinstellungen das richtige Mikrofon wählen. |
| Fenster öffnet nicht | Mit **`Start_FENIX_Debug.bat`** starten; die Fehlermeldung bleibt sichtbar. |
| Wachmodus geht nicht | Funktioniert nur unter Windows; `Setup.bat` erneut ausführen. |

Hinweis: Die Testskripte geben ihre Meldungen auf Türkisch aus.

## Sicherheit

- `config.yaml` enthält deine Schlüssel: **niemandem schicken, nicht auf GitHub hochladen.**
- Im Ordner `data` liegen Chats und Gedächtnis; auch das ist privat.
- Wurde ein Schlüssel sichtbar, **beim Anbieter löschen und neu erstellen**.
