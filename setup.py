from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="extract-chat",
    version="0.1.0",
    author="extract-chat maintainers",
    description="Extract ChatGPT conversations to Markdown/HTML with citations",
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=find_packages("src"),
    package_dir={"": "src"},
    python_requires=">=3.10",
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "extract-chat=extract_chat.cli:main",
        ],
    },
)
