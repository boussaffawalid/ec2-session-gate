"""Setup configuration for ssm-manager"""
from setuptools import setup, find_packages

setup(
    name="ssm-manager",
    version="1.0.0",
    description="Cross-platform AWS SSM tunnel/connection manager",
    packages=find_packages(),
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
)
