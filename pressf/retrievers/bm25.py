"""Pure Okapi BM25 without dependencies.

Used by the docs_folder and chunks_file adapters."""

from __future__ import annotations

import math
import re
from collections import Counter

from ..schemas import Chunk

_TOKEN_RE = re.compile(r"\w+", re.UNICODE)

K1 = 1.5
B = 0.75


def tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


class BM25Index:
    def __init__(self, docs: list[tuple[str, str]]):
        """docs: list(text, source)."""
        self.docs = docs
        self._doc_tokens = [Counter(tokenize(t)) for t, _ in docs]
        self._doc_lens = [sum(c.values()) for c in self._doc_tokens]
        self._avg_len = (sum(self._doc_lens) / len(self._doc_lens)) if docs else 0.0
        df: Counter[str] = Counter()
        for c in self._doc_tokens:
            df.update(c.keys())
        n = len(docs)
        self._idf = {
            term: math.log((n - d + 0.5) / (d + 0.5) + 1.0) for term, d in df.items()
        }

    def __len__(self) -> int:
        return len(self.docs)

    def search(self, query: str, top_k: int) -> list[Chunk]:
        q_terms = tokenize(query)
        if not q_terms or not self.docs:
            return []
        scores: list[float] = []
        for tokens, dlen in zip(self._doc_tokens, self._doc_lens):
            s = 0.0
            for term in q_terms:
                tf = tokens.get(term, 0)
                if tf == 0:
                    continue
                idf = self._idf.get(term, 0.0)
                denom = tf + K1 * (1 - B + B * dlen / self._avg_len)
                s += idf * tf * (K1 + 1) / denom
            scores.append(s)
        ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
        out: list[Chunk] = []
        for i in ranked[:top_k]:
            if scores[i] <= 0.0:
                break
            text, source = self.docs[i]
            out.append(Chunk(text=text, source=source, score=round(scores[i], 4)))
        return out
