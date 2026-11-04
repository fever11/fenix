# Core: MK-Agentic-System · Powered by FENIX Engine · (c) 2026 Mustafa Koç · GPL-3.0-only (LICENSE, NOTICE.md)
"""Testler için küçük, sahte bir MCP sunucusu: bir salt okunur, bir de silme aracı vardır. Hiçbir şeyi gerçekten silmez."""
from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations

srv = MCPServer("sahte")


@srv.tool(annotations=ToolAnnotations(read_only_hint=True))
def selamla(isim: str) -> str:
    """İsme selam verir."""
    return f"Merhaba {isim}"


@srv.tool(annotations=ToolAnnotations(read_only_hint=False, destructive_hint=True))
def sil(yol: str) -> str:
    """Bir dosyayı siliyormuş gibi yapar."""
    return f"SILINDI:{yol}"


if __name__ == "__main__":
    srv.run()
