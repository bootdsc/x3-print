import os
import sys

from . import server


def main():
    if sys.stdout is None:
        sys.stdout = sys.stderr = open(os.devnull, "w")
    srv, url = server.start()
    try:
        import webview
    except ImportError:
        webview = None
    if webview:
        webview.create_window("X3 Print", url, width=1280, height=860, min_size=(720, 560),
                              background_color="#0a0a0a")
        webview.start()
    else:
        import webbrowser
        webbrowser.open(url)
        print(f"X3 Print is running at {url} - press Ctrl+C to quit")
        try:
            srv.serve_forever()
        except KeyboardInterrupt:
            pass
    server.WORKER.cancel.set()
