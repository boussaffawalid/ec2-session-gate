"""Setup configuration for ec2-session-gate"""
from setuptools import setup, find_packages
from pathlib import Path

# Read the README file
readme_file = Path(__file__).parent / "README.md"
long_description = readme_file.read_text(encoding="utf-8") if readme_file.exists() else ""

# Read version from src/version.py (single source of truth)
version_file = Path(__file__).parent / "src" / "version.py"
version = None
if version_file.exists():
    with open(version_file, "r") as f:
        for line in f:
            if line.startswith("__version__"):
                version = line.split("=")[1].strip().strip('"').strip("'")
                break

if not version:
    raise RuntimeError("Could not find version in src/version.py")

setup(
    name="ec2-session-gate",
    version=version,
    description="Cross-platform AWS SSM tunnel/connection manager for EC2 instances",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Walid Boussafa",
    author_email="walid.boussafa@outlook.com",
    url="https://github.com/boussaffawalid/ec2-session-gate",
    license="MIT",
    packages=find_packages(),
    py_modules=["run"],
    python_requires=">=3.9",
    install_requires=[
        "Flask>=2.3",
        "PyYAML>=6.0",
        "boto3>=1.34",
        "botocore>=1.34",
        "pywebview>=4.0",
        "cryptography>=41.0",
        "psutil>=5.9.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.4.0",
            "pytest-mock>=3.11.0",
            "pytest-cov>=4.1.0",
        ],
    },
    include_package_data=True,
    package_data={
        "src": [
            "static/**/*",
            "static/templates/**/*",
            "defaults.json",
            "logging.yaml",
        ],
    },
    entry_points={
        "console_scripts": [
            "ec2-session-gate=run:main",
        ],
        "gui_scripts": [
            "ec2-session-gate-gui=run:main",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Intended Audience :: System Administrators",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Operating System :: Microsoft :: Windows",
        "Operating System :: MacOS",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: System :: Networking",
        "Topic :: System :: Systems Administration",
        "Topic :: Internet :: WWW/HTTP :: Dynamic Content",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    keywords="aws ec2 ssm session-manager ssh rdp port-forwarding tunnel",
    project_urls={
        "Bug Reports": "https://github.com/boussaffawalid/ec2-session-gate/issues",
        "Source": "https://github.com/boussaffawalid/ec2-session-gate",
        "Documentation": "https://github.com/boussaffawalid/ec2-session-gate#readme",
    },
)
