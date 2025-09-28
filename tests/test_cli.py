import sys
from pathlib import Path

from extract_chat import cli

SAMPLE_PATH = Path("tmp/PA-Paper/chatgpt_convo_686ab2a1-6578-8003-b0e6-79b76323e002.json")
TURN_ID = "c3df4f37-ab12-4ab6-a810-6b687a759b83"


def run_cli(arguments: list[str]) -> None:
    original = sys.argv
    try:
        sys.argv = arguments
        cli.main()
    finally:
        sys.argv = original


def test_cli_supports_jekyll_format(tmp_path: Path) -> None:
    output_dir = tmp_path / "jekyll"
    args = [
        "extract-chat",
        str(SAMPLE_PATH),
        "--format",
        "jekyll",
        "--jekyll-turn-id",
        TURN_ID,
        "--jekyll-base-slug",
        "2025-09-25-pa-paper",
        "--output",
        str(output_dir),
        "--force",
    ]
    run_cli(args)

    expected = output_dir / "2025-09-25-pa-paper-references.md"
    assert expected.exists()
    sections = list(output_dir.glob("2025-09-25-pa-paper-*.md"))
    assert sections, "Expected section markdown files to be written"
