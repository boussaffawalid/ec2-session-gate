# EC2 Session Gate

> **Secure EC2 instance management and connection gateway**  
> A modern, cross-platform application for managing AWS EC2 instances and establishing secure connections via AWS Systems Manager Session Manager.

[![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-2.3+-green.svg)](https://flask.palletsprojects.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

![EC2 Session Gate Screenshot](image/screenshot.png)

---

## 🚀 Overview

**EC2 Session Gate** simplifies secure access to your EC2 instances without exposing SSH ports or managing complex VPN configurations. Built on AWS Systems Manager Session Manager, it provides a seamless interface for SSH, RDP, and custom port forwarding connections.

### Why EC2 Session Gate?

- ✅ **Zero Open Ports** - No need to expose SSH ports or manage security groups
- ✅ **Secure by Default** - Uses AWS SSM Session Manager for encrypted connections
- ✅ **Cross-Platform** - Works seamlessly on Windows, macOS, and Linux
- ✅ **Easy to Use** - Intuitive web interface with desktop app option
- ✅ **Multi-Profile Support** - Switch between AWS profiles effortlessly
- ✅ **Auto Key Detection** - Automatically finds and uses SSH keys for password decryption

---

## ✨ Features

### Core Capabilities

- **🔐 SSH Connections**  
  Secure shell access via SSM port forwarding with automatic SSH key detection and path resolution

- **🖥️ RDP Support**  
  Remote desktop connections for Windows instances with automatic password decryption using SSH keys

- **🔌 Custom Port Forwarding**  
  Forward any port through SSM tunnels with flexible port selection and automatic port management

- **📊 Instance Management**  
  View, filter, and manage EC2 instances with real-time status updates and comprehensive instance details

- **🔑 Multi-Directory SSH Keys**  
  Support for multiple SSH key directories with automatic key lookup and path resolution

- **⚡ Auto-Refresh**  
  Automatic instance list refresh with configurable intervals

- **🎨 Modern UI**  
  Clean, responsive interface built with Bootstrap 5

---

## 📋 Prerequisites

Before you begin, ensure you have:

- **Python 3.9+** installed
- **AWS CLI v2** installed and configured
- **AWS Session Manager Plugin** installed
- **AWS credentials** configured (via `~/.aws/credentials` or environment variables)

### Installing Prerequisites

<details>
<summary><b>Install AWS CLI v2</b></summary>

**macOS:**
```bash
brew install awscli
```

**Linux:**
```bash
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install
```

**Windows:**
Download and run the installer from [AWS CLI Downloads](https://aws.amazon.com/cli/)
</details>

<details>
<summary><b>Install Session Manager Plugin</b></summary>

**macOS:**
```bash
brew install --cask session-manager-plugin
```

**Linux:**
```bash
curl "https://s3.amazonaws.com/session-manager-downloads/plugin/latest/linux_64bit/session-manager-plugin.rpm" -o "session-manager-plugin.rpm"
sudo yum install -y session-manager-plugin.rpm
```

**Windows:**
Download and run the installer from [Session Manager Plugin Downloads](https://docs.aws.amazon.com/systems-manager/latest/userguide/session-manager-working-with-install-plugin.html)
</details>

---

## 🛠️ Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/boussaffawalid/ec2-session-gate.git
   cd ec2-session-gate
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv .venv
   
   # Activate virtual environment
   # On macOS/Linux:
   source .venv/bin/activate
   # On Windows:
   .venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

### Installing from PyPI

Alternatively, install directly from PyPI:

```bash
pip install ec2-session-gate
```

After installation, launch the application:

```bash
# Desktop GUI mode (default)
ec2-session-gate-gui

# Or API/server mode
APP_MODE=api ec2-session-gate

# Or web browser mode
APP_MODE=web ec2-session-gate
```

---

## 🎮 Usage

### Running the Application

EC2 Session Gate supports three execution modes:

#### 🖥️ Desktop Mode (Recommended)
Launches a native desktop window using PyWebView.

```bash
python run.py
# or explicitly:
APP_MODE=desktop python run.py
```

#### 🌐 Web Browser Mode
Opens the application in your default web browser.

```bash
APP_MODE=web python run.py
```

#### 🔌 API/Server Mode
Runs the Flask server only (useful for remote access or API usage).

```bash
APP_MODE=api python run.py
```

The application will be available at `http://127.0.0.1:5000`

### Quick Start Guide

1. **Connect to AWS**
   - Select your AWS profile from the dropdown
   - Choose the AWS region
   - Click "Connect"
   - View your EC2 instances in the list

2. **Start a Connection**
   - **SSH**: Click the "SSH" button on an instance card
   - **RDP**: Click the "RDP" button (Windows instances only)
   - **Custom Port**: Click the "Port" button and specify remote/local ports

3. **Manage Connections**
   - View active connections in the sidebar
   - Copy connection details to clipboard
   - Terminate connections when done

### Advanced Features

#### Instance Filtering
Use the filter box to search instances by:
- Instance name
- Instance ID
- Instance type
- Instance state
- Operating system

Supports **regular expressions** for advanced filtering.

#### Port Selection
- **SSH/RDP**: Automatically uses the same local port as remote port (22 for SSH, 3389 for RDP)
- **Custom Ports**: Uses the same local port if available, otherwise falls back to configured range
- **Port Range**: Configurable in Preferences with OS-specific defaults:
  - **Windows**: 40000-40100 (below ephemeral port range)
  - **Linux/macOS**: 61000-61100 (above ephemeral port range)

---

## ⚙️ Configuration

### Preferences

Preferences are stored in:
- **Linux/macOS**: `~/.config/ec2-session-gate/preferences.json`
- **Windows**: `%APPDATA%\ec2-session-gate\preferences.json`

#### Available Settings

| Setting | Description | Default |
|---------|-------------|---------|
| **Port Range** | Port range for port forwarding | OS-specific (Windows: 40000-40100, Linux/macOS: 61000-61100) |
| **SSH Key Folders** | Directories where SSH keys are stored (one per line) | `~/.ssh` |
| **Logging Level** | Application log level | INFO |

#### SSH Key Configuration

Configure multiple SSH key directories in Preferences:
- Each folder path on its own line
- Supports `~` expansion (e.g., `~/.ssh`)
- Keys are automatically searched when decrypting Windows passwords
- SSH commands include the key path automatically

**Example:**
```
~/.ssh
~/Projects/keys
/path/to/custom/keys
```

---

## 📁 Project Structure

```
ec2-session-gate/
├── src/                          # Source code
│   ├── app.py                    # Flask app factory + blueprints
│   ├── api.py                    # REST API endpoints
│   ├── ui.py                     # UI routes
│   ├── aws_manager.py            # AWS SSM connection management
│   ├── preferences_handler.py    # User preferences
│   ├── health.py                 # Health check utilities
│   ├── utils.py                  # Utility functions
│   └── static/                   # Frontend assets
│       ├── css/                  # Stylesheets
│       ├── js/                   # JavaScript
│       └── templates/            # HTML templates
├── run.py                        # Application launcher
├── requirements.txt              # Python dependencies
├── pyproject.toml               # Project metadata
└── tests/                        # Test files
```

---

## 🔧 Development

### Running Tests

```bash
python -m pytest tests/
```

### Building Desktop App

#### Using PyInstaller (Standalone Executable)

```bash
# Install PyInstaller
pip install pyinstaller

# Build standalone executable
python build_standalone.py

# Or manually:
pyinstaller --onefile \
    --windowed \
    --add-data "src/static:src/static" \
    --add-data "src/defaults.json:src" \
    --add-data "src/logging.yaml:src" \
    --hidden-import=webview \
    --hidden-import=flask \
    run.py
```

The executable will be created in the `dist/` directory:
- **Windows**: `dist/ec2-session-gate.exe`
- **macOS**: `dist/ec2-session-gate.app`
- **Linux**: `dist/ec2-session-gate`

### Project Dependencies

- **Flask>=2.3** - Web framework
- **boto3>=1.34** - AWS SDK for Python
- **botocore>=1.34** - AWS SDK core library
- **PyYAML>=6.0** - YAML parsing for configuration
- **pywebview>=4.0** - Desktop application framework
- **cryptography>=41.0** - Password decryption for Windows instances
- **psutil>=5.9.0** - Process management and cleanup

---

## 🐛 Troubleshooting

### Common Issues

<details>
<summary><b>AWS CLI not found</b></summary>

**Solution:** Install AWS CLI v2 and ensure it's in your PATH.

Verify installation:
```bash
aws --version
```
</details>

<details>
<summary><b>Session Manager Plugin missing</b></summary>

**Solution:** Install the AWS Session Manager Plugin.

Verify installation:
```bash
session-manager-plugin
```
</details>

<details>
<summary><b>No AWS credentials detected</b></summary>

**Solution:** Configure AWS credentials via `aws configure` or environment variables.

```bash
aws configure
# or set environment variables:
export AWS_ACCESS_KEY_ID=your_access_key
export AWS_SECRET_ACCESS_KEY=your_secret_key
export AWS_DEFAULT_REGION=us-east-1
```
</details>

<details>
<summary><b>Port already in use</b></summary>

**Solution:** Adjust port range in Preferences or specify a different local port when starting a connection.
</details>

<details>
<summary><b>SSH key not found</b></summary>

**Solution:** Add SSH key directories in Preferences. Ensure keys have correct permissions:

```bash
chmod 600 ~/.ssh/your-key.pem
```
</details>

### Logs

Application logs are written to:
- **Development**: `src/app.log`
- **Production**: `~/.config/ec2-session-gate/logs/app.log`

View logs:
```bash
tail -f src/app.log
```

---

## 🤝 Contributing

Contributions, feedback, and improvement ideas are welcome!

### How to Contribute

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Contact

- **Maintainer**: Walid Boussafa
- **Email**: walid.boussafa@outlook.com
- **GitHub**: [@boussaffawalid](https://github.com/boussaffawalid/ec2-session-gate)

---

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 📦 Publishing to PyPI

### Installing from PyPI

Once published, users can install the package using:

```bash
pip install ec2-session-gate
```

After installation, the application can be launched with:

```bash
# Desktop GUI mode (default)
ec2-session-gate-gui

# Or API/server mode
APP_MODE=api ec2-session-gate

# Or web browser mode
APP_MODE=web ec2-session-gate
```

### Publishing a New Version

1. **Update version** in `setup.py` and `pyproject.toml`

2. **Install build tools**:
   ```bash
   pip install build twine
   ```

3. **Build the package**:
   ```bash
   make build
   # or: python -m build
   ```

4. **Test on TestPyPI** (optional):
   ```bash
   make publish-test
   # or: twine upload --repository testpypi dist/*
   ```

5. **Publish to PyPI**:
   ```bash
   make publish
   # or: twine upload dist/*
   ```

### Standalone Executable Distribution

To create standalone executables for distribution:

```bash
# Build standalone executable
make build-standalone
# or: python build_standalone.py
```

The executables will be in the `dist/` directory and can be distributed independently without requiring Python installation.

---

## 📚 Additional Resources

- [AWS Systems Manager Documentation](https://docs.aws.amazon.com/systems-manager/)
- [AWS Session Manager User Guide](https://docs.aws.amazon.com/systems-manager/latest/userguide/session-manager.html)
- [AWS CLI Documentation](https://docs.aws.amazon.com/cli/)

---

## 🎯 Roadmap

- [ ] Enhanced connection history
- [ ] Connection templates/presets
- [ ] Batch operations on instances
- [ ] Export connection details
- [ ] Dark mode support
- [ ] Mobile-responsive improvements

---

## 🙏 Acknowledgments

This project was inspired by [SSM Manager](https://github.com/mauroo82/ssm-manager), a Windows desktop application for managing AWS SSM sessions. EC2 Session Gate extends this concept with cross-platform support and additional features.

Built with:
- [Flask](https://flask.palletsprojects.com/) - Web framework
- [Bootstrap](https://getbootstrap.com/) - UI framework
- [Boto3](https://boto3.amazonaws.com/) - AWS SDK
- [PyWebView](https://pywebview.flowrl.com/) - Desktop app framework

---

**Made with ❤️ for the AWS community**
