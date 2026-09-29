"""Download a pinned public OPUS model; verify every file before enabling it."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import requests

from steelwatch.translate import MODEL, REVISION

FILES = {
    "README.md": "83eee2a6598751f746a057e10d5c9dfd71d6b0cf0146f9e6c1bb3ebd6e90959b",
    "vocab.json": "f1832ca38f7aa158b9a944ff583e4901e6b37d9d4ad9241f03838e636e9cfb03",
    "pytorch_model.bin": "69a1d6ec829cee349360b3b677ac0aa99a7d88822d1a6578370029efffdca3f5",
    "source.spm": "5775ddc9e3ff2fae91554da56468ad35ff56edaba870fea74447bc7234bfdaa8",
    "tokenizer_config.json": "5df181fba586b7cb37d429c13c4f96cb43fb11de7bb6489733d9eded32418179",
    "generation_config.json": "837839ed0534a27084f9b980fc33f47729052dd89cb26cca7ac830765ed30e49",
    "config.json": "bcae8ed74fed77fb51c58462b62397fee6b1a1a34aece79183a0dd02ad329e71",
    "target.spm": "81dc94efa84e4025ef38d25d5d07429fe41e3eb29d44003f1db6fe98487b0052",
}


def digest(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def main() -> None:
    target = Path(os.environ.get("STEELWATCH_MT_DIR", ".cache/opus-en-zh"))
    target.mkdir(parents=True, exist_ok=True)
    (target / "ready.json").unlink(missing_ok=True)
    for name, expected in FILES.items():
        path = target / name
        if path.is_file() and digest(path) == expected:
            continue
        temporary = path.with_suffix(path.suffix + ".part")
        with requests.get(
            f"https://huggingface.co/{MODEL}/resolve/{REVISION}/{name}",
            stream=True, timeout=(15, 30),
        ) as response:
            response.raise_for_status()
            size = 0
            with temporary.open("wb") as handle:
                for chunk in response.iter_content(1024 * 1024):
                    size += len(chunk)
                    if size > 400_000_000:
                        raise ValueError("translation model exceeds expected size")
                    handle.write(chunk)
        if digest(temporary) != expected:
            raise ValueError(f"translation model checksum mismatch: {name}")
        temporary.replace(path)
    (target / "ready.json").write_text(json.dumps({"model": MODEL, "revision": REVISION}))
    print("Verified offline English–Chinese model is ready.")


if __name__ == "__main__":
    main()
