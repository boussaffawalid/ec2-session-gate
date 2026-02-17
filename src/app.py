import os
import socket
import signal
import logging
import logging.config
import yaml
from flask import Flask, request
from pathlib import Path

logger = logging.getLogger(__name__)


def _find_free_port() -> int:
    """Find a random free port by letting OS assign one."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def get_server_port() -> int:
    """Get server port from environment variable or use default.
    If the configured port is in use, automatically finds a free port.
    Uses existing _is_port_free() from src.aws_manager.
    """
    from src.aws_manager import _is_port_free

    port_str = os.environ.get("EC2_SESSION_GATE_PORT") or os.environ.get("PORT")
    preferred_port = 5000

    if port_str:
        try:
            preferred_port = int(port_str)
            if not (1 <= preferred_port <= 65535):
                logger.warning("Port %s out of range, using default 5000", preferred_port)
                preferred_port = 5000
        except ValueError:
            logger.warning("Invalid port value %r, using default 5000", port_str)
            preferred_port = 5000

    if _is_port_free(preferred_port):
        logger.info("Using configured port %s", preferred_port)
        return preferred_port
    free_port = _find_free_port()
    logger.warning("Port %s is in use, using free port %s instead", preferred_port, free_port)
    return free_port


def create_app():
    base_dir = Path(__file__).resolve().parent
    app = Flask(__name__, static_folder=str(base_dir / "static"), template_folder=str(base_dir / "static" / "templates"))
    
    # CORS configuration - only allow localhost for security
    @app.after_request
    def after_request(response):
        # Only allow requests from localhost
        origin = request.headers.get('Origin', '')
        if origin.startswith('http://127.0.0.1') or origin.startswith('http://localhost'):
            response.headers['Access-Control-Allow-Origin'] = origin
            response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
            response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        return response

    # Logging: load YAML then adjust file handler path into user config dir
    # Skip file logging in test mode to avoid permission issues
    # Check both app config and environment variable for test mode
    is_testing = app.config.get('TESTING') or os.environ.get('FLASK_ENV') == 'testing' or os.environ.get('PYTEST_CURRENT_TEST')
    if is_testing:
        logging.basicConfig(level=logging.INFO)
    else:
        cfg = base_dir / "logging.yaml"
        if cfg.exists():
            with open(cfg, "r") as f:
                cfg_dict = yaml.safe_load(f)
            # Ensure log file lives under ~/.config/ec2-session-gate/logs
            log_dir = Path.home() / ".config" / "ec2-session-gate" / "logs"
            try:
                log_dir.mkdir(parents=True, exist_ok=True)
                # Set appropriate permissions on log directory (not world-readable)
                from .constants import LOG_DIR_PERMISSIONS, LOG_FILE_PERMISSIONS
                try:
                    os.chmod(log_dir, LOG_DIR_PERMISSIONS)
                except Exception:
                    pass  # Ignore permission errors on some systems
                # If a file handler exists, point it to our app.log
                try:
                    log_file = log_dir / "app.log"
                    cfg_dict["handlers"]["file"]["filename"] = str(log_file)
                    # Ensure log file has appropriate permissions
                    if log_file.exists():
                        try:
                            os.chmod(log_file, LOG_FILE_PERMISSIONS)
                        except Exception:
                            pass
                except Exception:
                    pass
                logging.config.dictConfig(cfg_dict)
            except (PermissionError, OSError):
                # If we can't create log directory (e.g., in tests), fall back to basic config
                logging.basicConfig(level=logging.INFO)
        else:
            logging.basicConfig(level=logging.INFO)
    from .version import __version__
    app.logger.info("Starting EC2 Session Gate", extra={"version": __version__})

    # Blueprints
    from src.api import api_bp, aws_manager
    from src.ui import ui_bp

    app.register_blueprint(ui_bp)
    app.register_blueprint(api_bp, url_prefix="/api")

    # Register shutdown handlers to cleanup connections
    def cleanup_connections(signum=None, frame=None):
        """Cleanup all active connections on shutdown."""
        app.logger.info(f"Received signal {signum} - terminating all active connections...")
        try:
            aws_manager.terminate_all()
        except Exception as e:
            app.logger.error(f"Error during connection cleanup: {e}", exc_info=True)
        app.logger.info("Cleanup complete")

    # Register signal handlers for graceful shutdown
    # Only register if we're in the main thread (not in a daemon thread)
    import threading
    if threading.current_thread() is threading.main_thread():
        try:
            signal.signal(signal.SIGINT, cleanup_connections)
            signal.signal(signal.SIGTERM, cleanup_connections)
            app.logger.info("Signal handlers registered for graceful shutdown")
        except (ValueError, OSError) as e:
            # Signal handlers might not work on all platforms/contexts
            app.logger.warning(f"Could not register signal handlers: {e}")
    
    # Register Flask teardown handler for when app context closes
    @app.teardown_appcontext
    def close_connections(error):
        """Cleanup connections when app context is torn down."""
        if error:
            app.logger.error(f"Error in app context: {error}")
        # Note: We don't cleanup here as connections should persist across requests
        # Only cleanup on actual app shutdown (SIGINT/SIGTERM)

    return app

if __name__ == "__main__":
    app = create_app()
    port = get_server_port()
    app.run(host="127.0.0.1", port=port, debug=True)
