# Ensure we can import from bin/pylib
import os
import sys
from typing import Any

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE_DIR, 'bin'))

from pylib.processors.citation_processor import CitationProcessor


class FakePart:
    def __init__(self, text: str):
        self.text = text


class FakeContent:
    def __init__(self, text: str):
        self.content_type = 'text'
        self.parts = [FakePart(text)]


class FakeMessage:
    def __init__(self, text: str, metadata: Any):
        self.content = FakeContent(text)
        self.metadata = metadata


class FakeTurn:
    def __init__(self, message: Any):
        self.message = message


def make_metadata():
    # Citations (metadata.citations):
    # - one exact match for 28,L249-L258 with title only
    # - one off-by-one end (257) for same ref_id; provides url only
    # - one invalid
    citations = [
        {
            'metadata': {
                'title': 'Exact Title',
                'url': '',
                'text': '',
                'pub_date': '2022-01-01',
                'extra': {'cited_message_idx': 28, 'start_line_num': 249, 'end_line_num': 258},
            },
        },
        {
            'metadata': {
                'title': '',
                'url': 'https://example.com/exact-or-near',
                'text': '',
                'pub_date': None,
                'extra': {'cited_message_idx': 28, 'start_line_num': 249, 'end_line_num': 257},
            },
        },
        {
            'metadata': {
                'title': 'Should be skipped',
                'extra': {'cited_message_idx': 99, 'start_line_num': 1, 'end_line_num': 2},
            },
            'invalid_reason': 'bad',
        },
    ]

    # Content references (metadata.content_references):
    # - one exact with snippet/text
    # - one invalid entry
    content_refs = [
        {
            'matched_text': 'Some context with marker  around it',
            'grouped_webpages': [
                {
                    'items': [
                        {
                            'title': '',
                            'url': 'https://example.com/fallback',
                            'snippet': 'Quoted snippet here',
                            'pub_date': '2021-12-31',
                            'attribution': 'Example Source',
                        }
                    ]
                }
            ],
        },
        {
            'matched_text': 'Noise ',
            'invalid': True,
        },
    ]

    class Meta(dict):
        # Allow both attribute and dict access
        def __getattr__(self, item):
            try:
                return self[item]
            except KeyError:
                raise AttributeError(item)

    return Meta({'citations': citations, 'content_references': content_refs})


def run_test():
    text = (
        "Intro text. "
        "Marker A:  and again . "
        "A different marker: ."
    )

    meta = make_metadata()
    message = FakeMessage(text=text, metadata=meta)
    turn = FakeTurn(message=message)

    proc = CitationProcessor()
    result = proc.get_references_data(turn=turn, ref_turn_counter=1)

    refs = result.get('references', [])
    # Verify markers were extracted by checking references include both keys
    keys_in_refs = { (r['ref_id'], r['start_line'], r['end_line']) for r in refs }
    assert (28, 249, 258) in keys_in_refs, 'Primary marker missing in references list'
    assert (5, 10, 15) in keys_in_refs, 'Secondary marker missing in references list'

    # Find the reference for (28,249,258) and check merged fields
    ref_28 = next((r for r in refs if r['ref_id'] == 28 and r['start_line'] == 249 and r['end_line'] == 258), None)
    assert ref_28, 'Merged reference for 28/249/258 not found in final list'
    assert ref_28['title'] == 'Exact Title', 'Title should come from citations'
    # url can come from tolerant citation or content_refs fallback; ensure non-empty
    assert ref_28['url'], 'URL expected to be filled from tolerant citation or content refs'
    assert ref_28['text'] == 'Quoted snippet here', 'Text/snippet should be filled from content refs'
    assert ref_28['attribution'] == 'Example Source', 'Attribution should be filled from content refs'

    print('OK: all assertions passed')


if __name__ == '__main__':
    run_test()


