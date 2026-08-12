from pathlib import Path
from types import SimpleNamespace

from extract_chat.tables import write_embedded_tables


def test_embedded_html_table_becomes_tsv(tmp_path: Path) -> None:
    message = SimpleNamespace(metadata={
        "ada_visualizations": [{"type": "table", "title": "My Table"}],
        "aggregate_result": {"data": {"text/html": "<table><tr><th>A</th><th>B</th></tr><tr><td>1</td><td>two</td></tr></table>"}},
    })
    conversation = SimpleNamespace(mapping={"turn": SimpleNamespace(message=message)})
    paths = write_embedded_tables(conversation, tmp_path)
    assert paths == [tmp_path / "my-table.tsv"]
    assert paths[0].read_text() == "A\tB\n1\ttwo\n"
