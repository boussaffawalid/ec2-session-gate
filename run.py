import os
import threading
import webbrowser
from src.app import create_app, get_server_port

app = create_app()


def run_server(port: int):
    """Run the Flask server in a background thread."""
    app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False)


def main():
    """Main entry point for the application."""
    mode = os.environ.get("APP_MODE", "desktop")  # default is now desktop
    port = get_server_port()

    if mode == "api":
        print("Running in API/server mode...")
        app.run(host="127.0.0.1", port=port, debug=False)

    elif mode == "web":
        print("Launching EC2 Session Gate in browser mode...")
        threading.Thread(target=lambda: app.run(host="127.0.0.1", port=port), daemon=True).start()
        webbrowser.open(f"http://127.0.0.1:{port}")

    elif mode == "desktop":
        import webview
        import atexit
        import signal
        from src.api import aws_manager

        class DesktopApi:
            def save_file(self, filename, content):
                """Show a native Save As dialog and write the file."""
                import platform
                import subprocess
                if platform.system() == 'Darwin':
                    # SAVE_DIALOG is broken in pywebview on macOS; use AppleScript instead
                    safe_name = filename.replace('"', '\\"')
                    proc = subprocess.run(
                        ['osascript',
                         '-e', f'set f to choose file name default name "{safe_name}" with prompt "Save connections as:"',
                         '-e', 'POSIX path of f'],
                        capture_output=True, text=True
                    )
                    if proc.returncode != 0:
                        return {'status': 'cancelled'}
                    path = proc.stdout.strip()
                else:
                    result = webview.windows[0].create_file_dialog(webview.SAVE_DIALOG, save_filename=filename)
                    if not result or not result[0]:
                        return {'status': 'cancelled'}
                    path = result[0]
                    if os.path.isdir(path):
                        path = os.path.join(path, filename)
                with open(path, 'w', encoding='utf-8') as f:
                    f.write(content)
                return {'status': 'success', 'path': path}

        def cleanup_on_exit():
            """Cleanup connections when desktop app exits."""
            print("Cleaning up connections...")
            try:
                aws_manager.terminate_all()
            except Exception as e:
                print(f"Error during cleanup: {e}")

        def signal_handler(signum, frame):
            """Handle signals in desktop mode."""
            cleanup_on_exit()
            import sys
            sys.exit(0)

        atexit.register(cleanup_on_exit)
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        print("Launching EC2 Session Gate in desktop window (PyWebView)...")
        threading.Thread(target=run_server, args=(port,), daemon=True).start()
        webview.create_window("EC2 Session Gate", f"http://127.0.0.1:{port}", width=1280, height=800, js_api=DesktopApi())

        try:
            webview.start(debug=False)
        finally:
            # Cleanup after webview window closes
            cleanup_on_exit()

    else:
        print(f"Unknown APP_MODE={mode}")

if __name__ == "__main__":
    main()
