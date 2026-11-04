# FENIX Setup Guide (English)

Takes about **15 minutes**. No technical knowledge needed; just follow the steps in order.

## What you need

| | |
|---|---|
| Computer | Windows 10 or 11 |
| Program | Python 3.12 (free) |
| Key | Gemini API key (free, required) |
| Optional | Groq API key (free; faster chat and better speech recognition) |
| Optional | NVIDIA API key (free; backup chat when Groq runs out) — https://build.nvidia.com |
| Optional | Tavily API key (free monthly quota; better web search) — https://app.tavily.com |

## 1. Download FENIX

1. On the GitHub page press the green **Code** button → **Download ZIP**.
2. Right-click the ZIP → **Extract All**. Put the folder somewhere simple, e.g. `Documents\fenix`.

## 2. Install Python

1. Download **Python 3.12** from https://www.python.org/downloads/.
2. On the first installer screen **tick "Add python.exe to PATH"**, then click **Install Now**.

## 3. Get your Gemini key

1. Go to https://aistudio.google.com/apikey and sign in with your Google account.
2. **Create API key** → copy the key. **Never share** this key.
3. (Optional) You can also get a Groq key at https://console.groq.com/keys.

## 4. Run the setup

1. Double-click **`Setup.bat`** in the FENIX folder.
   - If you see "Windows protected your PC": click **More info → Run anyway**.
2. Choose your language in the window (1-6).
3. If Python is missing, the setup tells you and offers to install it automatically.
4. Wait while the packages install (5-10 minutes). A **FENIX** shortcut is added to your desktop.

## 5. Start FENIX and paste your key

- Double-click the **FENIX** icon on your desktop.
- On first start a small **API key** window appears: paste your Gemini key (and Groq if you have one) and click **Save and start**. No file editing needed.
- You can change the language later in **⚙️ Settings**.

## Quick usage

| What | How |
|---|---|
| Text chat | Type at the bottom, press **Enter** |
| Voice chat | **🎤 Push-to-talk** button or **F9** |
| Attach a file / image | **📎**, drag and drop, or **Ctrl+V** |
| Mode | **Safe** (chat only) · **Normal** (everyday tasks, asks before risky ones) · **Devil** (deep research, reports) |
| Emergency stop | **Ctrl+Alt+Q** or hold the mouse in the top-left corner for 1.5 s |

FENIX **asks for approval in every mode** before risky actions (delete, shut down, download, etc.).

## Problems?

| Symptom | Fix |
|---|---|
| "Python not found" | Reinstall Python and tick **Add python.exe to PATH**. |
| Key error / no replies | Run **`Connection_Test.bat`**; it tells you which key fails. |
| Microphone not heard | Run **`Microphone_Test.bat`**. Pick the right mic in Windows sound settings. |
| Window doesn't open | Start with **`Start_FENIX_Debug.bat`**; the error message stays on screen. |
| Watch mode doesn't work | It only works on Windows; run `Setup.bat` again. |

Note: the helper test scripts print their messages in Turkish.

## Security

- `config.yaml` holds your keys: **never send it to anyone or upload it to GitHub.**
- The `data` folder holds your chats and memory; it is personal too.
- If your key was ever exposed, **delete it on the provider's site and create a new one**.
