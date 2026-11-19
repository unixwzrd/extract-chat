"""Use runtime-local resources, never build-environment paths or downloads."""

import os
import sys
from pathlib import Path
import zoneinfo

import tiktoken.load

os.environ["TIKTOKEN_CACHE_DIR"] = str(Path(sys._MEIPASS) / "tokenizer-cache")

# Conda's compiled TZPATH points inside its development environment. At frozen
# startup, select macOS's OS-maintained database before any ZoneInfo instances
# exist. This also keeps Foundation's timezone picker and Python on the same
# offline data without asking for access to the developer's Conda installation.
if sys.platform == "darwin":
    zoneinfo.reset_tzpath(["/usr/share/zoneinfo"])


def deny_tokenizer_download(path: str) -> bytes:
    raise RuntimeError(f"Tokenizer data is not bundled for this encoding: {path}")


# read_file_cached still reads a prevalidated local cache entry. A missing or
# corrupt entry must fail, not turn a conversion into a network request.
tiktoken.load.read_file = deny_tokenizer_download
