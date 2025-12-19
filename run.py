import os
import threading
import webbrowser
from src.app import create_app

app = create_app()

def run_server():
    """Run the Flask server in a background thread."""
    app.run(host="127.0.0.1", port=5000, debug=False, use_reloader=False)

def main():
    """Main entry point for the application."""
    mode = os.environ.get("APP_MODE", "desktop")  # default is now desktop

    if mode == "api":
        print("Running in API/server mode...")
        app.run(host="127.0.0.1", port=5000, debug=False)

    elif mode == "web":
        print("Launching EC2 Session Gate in browser mode...")
        threading.Thread(target=lambda: app.run(host="127.0.0.1", port=5000)).start()
        webbrowser.open("http://127.0.0.1:5000")

    elif mode == "desktop":
        import webview
        import atexit
        import signal
        from src.api import aws_manager
        
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
            # Exit gracefully
            import sys
            sys.exit(0)
        
        # Register cleanup function to run on exit
        atexit.register(cleanup_on_exit)
        
        # Register signal handlers for desktop mode
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        print("Launching EC2 Session Gate in desktop window (PyWebView)...")
        threading.Thread(target=run_server, daemon=True).start()
        # Create a PyWebView window
        webview.create_window("EC2 Session Gate", "http://127.0.0.1:5000", width=1280, height=800)
        
        try:
            webview.start(debug=False)
        finally:
            # Cleanup after webview window closes
            cleanup_on_exit()

    else:
        print(f"Unknown APP_MODE={mode}")

if __name__ == "__main__":
    main()
