"""Local static dashboard server."""
from __future__ import annotations

from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


def serve(directory: Path, host: str = "127.0.0.1", port: int = 8000) -> None:
    handler = partial(SimpleHTTPRequestHandler, directory=str(directory.resolve()))
    server = ThreadingHTTPServer((host, port), handler)
    print(f"Dashboard: http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
