import os
import sys
from typing import Any

# Workspace root is two levels up from this file
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE_DIR, 'src'))

from extract_chat.processors.citation_processor import CitationProcessor
from extract_chat.schemas.conversation import Conversation


def has_refs(message: Any) -> bool:
    meta = getattr(message, 'metadata', None)
    if not meta:
        return False
    try:
        if hasattr(meta, 'citations') and getattr(meta, 'citations'):
            return True
    except Exception:
        pass
    try:
        if hasattr(meta, 'content_references') and getattr(meta, 'content_references'):
            return True
    except Exception:
        pass
    # dict-style fallback
    try:
        if hasattr(meta, '__getitem__'):
            if meta.get('citations'):
                return True
            if meta.get('content_references'):
                return True
    except Exception:
        pass
    return False


def summarize_refs(refs_block: dict) -> dict:
    refs = refs_block.get('references', []) if refs_block else []
    total = len(refs)
    filled_title = sum(1 for r in refs if (r.get('title') or '').strip())
    filled_url = sum(1 for r in refs if (r.get('url') or '').strip())
    filled_text = sum(1 for r in refs if (r.get('text') or '').strip())
    empty_all = sum(1 for r in refs if not ((r.get('title') or r.get('url') or r.get('text'))))
    return {
        'total': total,
        'filled_title': filled_title,
        'filled_url': filled_url,
        'filled_text': filled_text,
        'empty_all': empty_all,
    }


def summarize_metadata_fields(message: Any, proc: CitationProcessor) -> dict:
    meta = getattr(message, 'metadata', None)
    if not meta:
        return {'citations': 0, 'cit_title': 0, 'cit_url': 0, 'cit_text': 0,
                'content_refs': 0, 'cr_title': 0, 'cr_url': 0, 'cr_text': 0}

    # Access lists via attr or dict
    citations = []
    if hasattr(meta, 'citations') and getattr(meta, 'citations') is not None:
        citations = getattr(meta, 'citations')
    elif hasattr(meta, '__getitem__'):
        citations = meta.get('citations', [])

    content_refs = []
    if hasattr(meta, 'content_references') and getattr(meta, 'content_references') is not None:
        content_refs = getattr(meta, 'content_references')
    elif hasattr(meta, '__getitem__'):
        content_refs = meta.get('content_references', [])

    cit_title = cit_url = cit_text = 0
    valid_citations = 0
    for raw in citations or []:
        entry = raw if isinstance(raw, dict) else (raw.dict() if hasattr(raw, 'dict') else {})
        if not entry or entry.get('invalid_reason'):
            continue
        valid_citations += 1
        data = proc.extract_data(entry, is_citation=True)
        if (data.get('title') or '').strip():
            cit_title += 1
        if (data.get('url') or '').strip():
            cit_url += 1
        if (data.get('text') or '').strip():
            cit_text += 1

    cr_title = cr_url = cr_text = 0
    valid_content_refs = 0
    for raw in content_refs or []:
        entry = raw if isinstance(raw, dict) else (raw.dict() if hasattr(raw, 'dict') else {})
        if not entry or entry.get('invalid') is True:
            continue
        valid_content_refs += 1
        data = proc.extract_data(entry, is_citation=False)
        if (data.get('title') or '').strip():
            cr_title += 1
        if (data.get('url') or '').strip():
            cr_url += 1
        if (data.get('text') or '').strip():
            cr_text += 1

    return {
        'citations': valid_citations,
        'cit_title': cit_title,
        'cit_url': cit_url,
        'cit_text': cit_text,
        'content_refs': valid_content_refs,
        'cr_title': cr_title,
        'cr_url': cr_url,
        'cr_text': cr_text,
    }


def main(json_path: str) -> None:
    with open(json_path, 'r', encoding='utf-8') as f:
        convo = Conversation.model_validate_json(f.read())
    proc = CitationProcessor()

    ref_turn_counter = 0
    print(f"REPORT: scanning {len(convo.mapping)} turns")

    global_seq = 1
    seq_map = {}

    for turn_id, turn in convo.mapping.items():
        message = getattr(turn, 'message', None)
        if not message:
            continue
        if not has_refs(message):
            continue
        ref_turn_counter += 1
        refs_block, global_seq = proc.get_references_data(
            turn=turn,
            ref_turn_counter=ref_turn_counter,
            start_seq=global_seq,
            existing_sequences=seq_map,
        )
        summary = summarize_refs(refs_block)
        meta_summary = summarize_metadata_fields(message, proc)
        print(f"TURN {ref_turn_counter} id={turn_id}")
        print(f"  references: {summary['total']} | title:{summary['filled_title']} url:{summary['filled_url']} text:{summary['filled_text']} empty_all:{summary['empty_all']}")
        print(f"  meta.citations: {meta_summary['citations']} | title:{meta_summary['cit_title']} url:{meta_summary['cit_url']} text:{meta_summary['cit_text']}")
        print(f"  meta.content_refs: {meta_summary['content_refs']} | title:{meta_summary['cr_title']} url:{meta_summary['cr_url']} text:{meta_summary['cr_text']}")
        # Print up to 3 samples with fields
        refs = refs_block.get('references', [])
        for r in refs[:3]:
            print(
                f"   - seq={r.get('seq')} key=({r.get('ref_id')},L{r.get('start_line')}-L{r.get('end_line')}) "
                f"title='{(r.get('title') or '')[:60]}' url='{(r.get('url') or '')[:60]}' text='{(r.get('text') or '')[:60]}'"
            )

    print("REPORT: done")


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python utils/refs_report.py <path-to-json>")
        sys.exit(2)
    main(sys.argv[1])
