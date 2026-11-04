# Guía de instalación de FENIX (Español)

Unos **15 minutos**. No hace falta saber de informática; sigue los pasos en orden.

## Qué necesitas

| | |
|---|---|
| Equipo | Windows 10 u 11 |
| Programa | Python 3.12 (gratis) |
| Clave | Clave de API de Gemini (gratis, obligatoria) |
| Opcional | Clave de API de Groq (gratis; chat más rápido y mejor reconocimiento de voz) |
| Opcional | Clave de API de NVIDIA (gratis; chat de respaldo cuando Groq se agota) — https://build.nvidia.com |
| Opcional | Clave de API de Tavily (cuota mensual gratuita; mejor búsqueda web) — https://app.tavily.com |

## 1. Descarga FENIX

1. En la página de GitHub pulsa el botón verde **Code** → **Download ZIP**.
2. Clic derecho en el ZIP → **Extraer todo**. Pon la carpeta en un sitio sencillo, p. ej. `Documentos\fenix`.

## 2. Instala Python

1. Descarga **Python 3.12** desde https://www.python.org/downloads/.
2. En la primera pantalla del instalador **marca "Add python.exe to PATH"** y luego **Install Now**.

## 3. Consigue tu clave de Gemini

1. Entra en https://aistudio.google.com/apikey con tu cuenta de Google.
2. **Create API key** → copia la clave. **No la compartas nunca**.
3. (Opcional) Puedes conseguir una clave de Groq en https://console.groq.com/keys.

## 4. Ejecuta la instalación

1. Haz doble clic en **`Setup.bat`** dentro de la carpeta de FENIX.
   - Si aparece «Windows protegió su PC»: **Más información → Ejecutar de todas formas**.
2. Elige tu idioma en la ventana (1-6).
3. Si falta Python, la instalación te lo dice y ofrece instalarlo automáticamente.
4. Espera mientras se instalan los paquetes (5-10 minutos). Se añade un acceso directo **FENIX** al escritorio.

## 5. Inicia FENIX y pega tu clave

- Haz doble clic en el icono **FENIX** del escritorio.
- En el primer inicio aparece una pequeña ventana **Clave de API**: pega tu clave de Gemini (y la de Groq si tienes) y pulsa **Guardar e iniciar**. No hace falta editar archivos.
- Puedes cambiar el idioma luego en **⚙️ Ajustes**.

## Uso rápido

| Qué | Cómo |
|---|---|
| Chat escrito | Escribe abajo, **Intro** |
| Chat por voz | Botón **🎤 Pulsar para hablar** o **F9** |
| Adjuntar archivo / imagen | **📎**, arrastrar y soltar o **Ctrl+V** |
| Modo | **Seguro** (solo chat) · **Normal** (tareas diarias, pregunta antes de lo arriesgado) · **Devil** (investigación profunda, informes) |
| Parada de emergencia | **Ctrl+Alt+Q** o deja el ratón 1,5 s en la esquina superior izquierda |

Antes de acciones arriesgadas (borrar, apagar, descargar, etc.) FENIX **pide aprobación en todos los modos**.

## ¿Problemas?

| Síntoma | Solución |
|---|---|
| «No se encuentra Python» | Reinstala Python y marca **Add python.exe to PATH**. |
| Error de clave / no responde | Ejecuta **`Connection_Test.bat`**; te dice qué clave falla. |
| El micrófono no oye | Ejecuta **`Microphone_Test.bat`**. Elige el micrófono correcto en la configuración de sonido de Windows. |
| La ventana no se abre | Inicia con **`Start_FENIX_Debug.bat`**; el mensaje de error queda en pantalla. |
| El modo guardia no funciona | Solo funciona en Windows; vuelve a ejecutar `Setup.bat`. |

Nota: los scripts de prueba muestran sus mensajes en turco.

## Seguridad

- `config.yaml` guarda tus claves: **no se lo envíes a nadie ni lo subas a GitHub.**
- La carpeta `data` guarda tus chats y tu memoria; también es personal.
- Si una clave quedó expuesta, **bórrala en la web del proveedor y crea una nueva**.
