"""Regression: CriticMarkup id/by/at meta must parse (JS reMeta \\s fix)."""

from __future__ import annotations

import re
import unittest


RE_META = r'\{id="([^"]*)"\s+by="([^"]*)"\s+at="([^"]*)"\}'
RE_HC = re.compile(
    r"\{==([\s\S]*?)==\}\{>>([\s\S]*?)<<\}(?:" + RE_META + r")?",
    re.MULTILINE,
)


def extract_ids(md: str) -> list[str]:
    return [m.group(3) for m in RE_HC.finditer(md)]


class TestExtractMarksMeta(unittest.TestCase):
    def test_meta_id_parsed(self) -> None:
        md = '{==phrase==}{>>note<<}{id="c7" by="qa" at="2026-10-30T12:00:00Z"}'
        self.assertEqual(extract_ids(md), ["c7"])


if __name__ == "__main__":
    unittest.main()
