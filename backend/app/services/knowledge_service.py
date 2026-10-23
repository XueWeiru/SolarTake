# -*- coding: utf-8 -*-
"""知識庫檢索：啟動時讀入 knowledge/ 資料夾的 .md 檔，依 `## 標題` 切成段落，
提問時用「字元雙連詞 + 稀有度加權」找出最相關的段落。
不需要額外套件；中文不用斷詞也能運作。要升級成語意搜尋時，只需替換 search()。"""

import math
import re
from dataclasses import dataclass
from pathlib import Path

DEFAULT_DIR = Path(__file__).resolve().parents[1] / "knowledge"
_PUNCT = re.compile(r"[\s，。！？、；：,.!?()（）「」『』\-—#*_`\"'>]")


@dataclass
class Chunk:
    source: str   # 檔名
    title: str    # 段落標題
    text: str     # 段落內容


def _bigrams(text: str) -> set[str]:
    s = _PUNCT.sub("", text.lower())
    return {s[i:i + 2] for i in range(len(s) - 1)}


class KnowledgeBase:
    def __init__(self, directory: Path = DEFAULT_DIR, max_chunk_chars: int = 800):
        self.chunks: list[Chunk] = []
        for path in sorted(Path(directory).glob("*.md")):
            self.chunks.extend(self._split(path, max_chunk_chars))
        self._grams = [_bigrams(c.title + c.text) for c in self.chunks]
        n = len(self.chunks)
        df: dict[str, int] = {}
        for grams in self._grams:
            for g in grams:
                df[g] = df.get(g, 0) + 1
        # 越少段落出現的詞越有辨識度（「是否」「可以」這類常見詞權重低）
        self._idf = {g: math.log((n + 1) / (d + 0.5)) + 1 for g, d in df.items()}

    @staticmethod
    def _split(path: Path, limit: int) -> list[Chunk]:
        chunks, title, buf = [], path.stem, []

        def flush():
            body = "\n".join(buf).strip()
            if body:
                chunks.append(Chunk(path.name, title, body[:limit]))

        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith("## "):
                flush()
                title, buf = line[3:].strip(), []
            elif not line.startswith("# ") and not line.startswith(">"):
                buf.append(line)
        flush()
        return chunks

    def search(self, query: str, k: int = 3, min_matches: int = 2) -> list[Chunk]:
        q = _bigrams(query)
        scored = []
        for chunk, grams in zip(self.chunks, self._grams):
            hit = q & grams
            if len(hit) >= min_matches:  # 至少要有 2 組詞重疊，避免湊巧命中
                scored.append((sum(self._idf[g] for g in hit), chunk))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [c for _, c in scored[:k]]
