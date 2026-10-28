"""Exact quote spans and closed citation IDs cannot manufacture evidence."""
import json

import pytest

from documentary.core import Blocked
from documentary.research import fact_check, write_script
from documentary.search import quote_candidates


@pytest.mark.parametrize('text', [
    'Original synthetic evidence includes curly “quotation marks”, an apostrophe’s glyph, and punctuation. ' * 12,
    '這是虛構原文，只用於檢查全形標點「引句」與字元位置，不是真實遊戲資料。' * 12,
])
def test_source_quote_spans_are_exact_bounded_and_language_independent(text):
    candidates = quote_candidates(text, {'english_topic': 'synthetic evidence', 'game': '虛構原文'})
    assert candidates
    assert sum(len(q['text']) for q in candidates) <= 6000
    assert all(text[q['start']:q['end']] == q['text'] and 24 <= len(q['text'].strip()) <= 250 for q in candidates)


def test_unknown_quote_id_is_rejected_not_fuzzy_repaired(tmp_path):
    class Model:
        def json(self, *a): return {'quote_ids': ['Q999999']}
    sources = [{'id': 'S1', 'url': 'https://fixture.example.org', 'text': 'Explicit synthetic evidence for an invalid-ID test. ' * 10}]
    with pytest.raises(Blocked) as exc:
        fact_check(Model(), {'english_topic': 'synthetic evidence'}, sources, tmp_path)
    assert exc.value.code == 'EVIDENCE_INVALID'
    assert json.loads((tmp_path / 'source_assessments.json').read_text())['S1']['status'] == 'INVALID_SELECTION'


def test_citation_ids_are_resolved_from_source_bytes_and_audit_still_required(tmp_path):
    sources = [{'id': f'S{i}', 'url': f'https://publisher{i}.example.{suffix}/story',
                'text': f'Publisher {i} reports a completely fictional fixture fact for testing evidence mechanics. ' * 5} for i, suffix in ((1, 'org'), (2, 'net'))]
    class Model:
        def json(self, instruction, payload):
            if 'Select up to 3' in instruction:
                return {'quote_ids': ['Q1']}
            if 'Build a conservative' in instruction:
                return {'claims': [{'id': f'C{i}', 'statement': '僅合成測試', 'date': None,
                    'evidence': [{'source_id': 'S1', 'quote_id': 'Q1'}, {'source_id': 'S2', 'quote_id': 'Q1'}]} for i in range(4)]}
            return {'claims': [{'id': f'C{i}', 'supported': False, 'independent_sources': True, 'reason': 'Explicit fixture veto'} for i in range(4)]}
    with pytest.raises(Blocked) as exc:
        fact_check(Model(), {'english_topic': 'fictional fixture'}, sources, tmp_path)
    assert exc.value.code == 'FACT_CHECK_FAILED'
    resolved = json.loads((tmp_path / 'evidence_resolved.json').read_text())
    for claim in resolved['claims']:
        for e in claim['evidence']:
            source = next(s for s in sources if s['id'] == e['source_id'])
            assert source['text'][e['source_start']:e['source_end']] == e['quote']
    assert not (tmp_path / 'evidence.json').exists()


def test_script_must_answer_requested_topic_even_when_coherent(tmp_path):
    class Model:
        chapter = 0
        def json(self, instruction, payload):
            if 'ONE chapter' in instruction:
                self.chapter += 1
                return {'scenes': [{'narration': f'第{self.chapter}章第{i}段：' + '這是虛構的合成測試敘事，只驗證程式的腳本與主題門檻。' * 3,
                                   'claim_ids': ['C1'], 'visual_need': 'synthetic fixture', 'footage_queries': ['synthetic fixture']} for i in range(6)]}
            if 'Audit each narrated' in instruction:
                return {'scenes': [{'id': s['id'], 'supported': True, 'original': True, 'reason': 'Explicit fixture'} for s in payload['scenes']]}
            return {'coherent': True, 'repetitive': False, 'answers_topic': False, 'reason': 'The coherent fixture does not answer the requested topic'}
    with pytest.raises(Blocked) as exc:
        write_script(Model(), {'game': 'Synthetic', 'english_topic': 'fictional topic'}, {'claims': [{'id': 'C1'}], 'timeline': []}, 12, tmp_path)
    assert exc.value.code == 'SCRIPT_AUDIT_FAILED'
    assert not (tmp_path / 'script.json').exists()
