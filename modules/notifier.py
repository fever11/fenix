# Core: MK-Agentic-System · Powered by FENIX Engine · (c) 2026 Mustafa Koç · All rights reserved
"""
Windows bildirimi (v5.7.3)
--------------------------
Ek paket gerektirmez: Windows 10/11'in kendi bildirim sistemini (toast) PowerShell üzerinden kullanır.
Bildirim ekranın sağ altında çıkar ve Bildirim Merkezi'nde kalır. FENIX penceresi arkadayken ya da
simge durumundayken önemli bir şeyi kaçırmaman için kullanılır.

Bildirim gösterilemezse (Windows dışı, eski sürüm, Odaklanma Yardımı açık vb.) sessizce False döner;
uygulama hiçbir zaman bu yüzden durmaz.
"""
import base64
import os
import subprocess
import threading
from xml.sax.saxutils import escape as _xml_escape

# Windows PowerShell'in kayıtlı uygulama kimliği: ayrı bir kurulum/kayıt gerektirmeden bildirim göstermeyi sağlar.
_APP_ID = r"{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe"


def build_script(title: str, body: str) -> str:
    """Bildirimi gösteren PowerShell betiği. Metinler XML'e göre kaçırılır, betik tek tırnakla gömülür."""
    try:
        from .i18n import tr
        title, body = tr(title or "FENIX"), tr(body or "")
    except Exception:
        pass
    title = _xml_escape(str(title or "FENIX"))[:120]
    body = _xml_escape(str(body or ""))[:400]
    xml = ("<toast><visual><binding template='ToastGeneric'>"
           f"<text>{title}</text><text>{body}</text>"
           "</binding></visual><audio src='ms-winsoundevent:Notification.Default'/></toast>")
    xml_ps = xml.replace("'", "''")
    return (
        "$ErrorActionPreference='Stop';"
        "[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType=WindowsRuntime] | Out-Null;"
        "[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType=WindowsRuntime] | Out-Null;"
        "$x = New-Object Windows.Data.Xml.Dom.XmlDocument;"
        f"$x.LoadXml('{xml_ps}');"
        "$t = New-Object Windows.UI.Notifications.ToastNotification $x;"
        f"[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('{_APP_ID}').Show($t)"
    )


def show_toast(title: str, body: str, timeout: int = 15) -> bool:
    """Bildirimi gösterir (bekler). Başarılıysa True."""
    if os.name != "nt":
        return False
    enc = base64.b64encode(build_script(title, body).encode("utf-16-le")).decode("ascii")
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-WindowStyle", "Hidden",
                            "-EncodedCommand", enc],
                           capture_output=True, timeout=timeout, creationflags=subprocess.CREATE_NO_WINDOW)
        return r.returncode == 0
    except Exception:
        return False


def show_toast_async(title: str, body: str) -> None:
    """Arayüzü bekletmeden arka planda gösterir."""
    threading.Thread(target=show_toast, args=(title, body), daemon=True).start()
