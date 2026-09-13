"""Exact token counts using the pinned local embedding tokenizer."""

from tokenizers import Tokenizer

from byod.config import Config
from byod.model_files import Progress, artifact


class TokenCounter:
    def __init__(self, config: Config, progress: Progress | None = None) -> None:
        self.tokenizer = Tokenizer.from_file(str(artifact(config, progress=progress)))
        self.tokenizer.no_truncation()
        self.tokenizer.no_padding()

    def count(self, text: str) -> int:
        return len(self.tokenizer.encode(text, add_special_tokens=False).ids)

    def split(self, text: str, budget: int) -> list[str]:
        if budget < 1:
            raise ValueError("Token budget must be positive")
        # Slice source offsets instead of decoding IDs, preserving punctuation/case.
        parts: list[str] = []
        remaining = text
        while self.count(remaining) > budget:
            encoded = self.tokenizer.encode(remaining, add_special_tokens=False)
            end = encoded.offsets[budget - 1][1]
            if end == 0:
                raise ValueError("Tokenizer produced an empty span")
            parts.append(remaining[:end])
            remaining = remaining[end:].lstrip()
        if remaining:
            parts.append(remaining)
        return parts
