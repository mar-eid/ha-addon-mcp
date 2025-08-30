"""
Setup configuration for MCP Server
"""
from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="ha-mcp-server",
    version="0.5.0",
    author="mar-eid",
    description="Model Context Protocol server for Home Assistant historical data",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/mar-eid/ha-addon-mcp",
    packages=find_packages(where="mcp-server"),
    package_dir={"": "mcp-server"},
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Home Automation",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    python_requires=">=3.9",
    install_requires=[
        "mcp>=1.1.2",
        "asyncpg>=0.29.0",
        "psycopg2-binary>=2.9.9",
        "python-dateutil>=2.8.2",
    ],
    extras_require={
        "dev": [
            "pytest>=7.4.3",
            "pytest-asyncio>=0.21.1",
            "pytest-cov>=4.1.0",
            "pytest-mock>=3.12.0",
            "black>=23.12.0",
            "flake8>=6.1.0",
            "mypy>=1.7.1",
        ],
    },
    entry_points={
        "console_scripts": [
            "ha-mcp-server=server:main",
        ],
    },
)
