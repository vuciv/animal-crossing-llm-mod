#!/usr/bin/env python3
"""
Setup script for Animal Crossing LLM Mod
"""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="animal-crossing-llm-mod",
    version="1.0.0",
    author="Animal Crossing Modding Community",
    description="AI-powered dialogue generation for Animal Crossing using LLMs",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/animal-crossing-llm-mod",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: End Users/Desktop",
        "Topic :: Games/Entertainment",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    python_requires=">=3.8",
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "ac-llm=ac_parser_encoder:main",
        ],
    },
    keywords="animal crossing, llm, ai, mod, dolphin, emulator, game",
    project_urls={
        "Bug Reports": "https://github.com/yourusername/animal-crossing-llm-mod/issues",
        "Source": "https://github.com/yourusername/animal-crossing-llm-mod",
        "Documentation": "https://github.com/yourusername/animal-crossing-llm-mod#readme",
    },
)
