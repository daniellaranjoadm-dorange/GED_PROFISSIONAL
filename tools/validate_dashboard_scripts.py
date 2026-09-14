"""Valida scripts HTML respeitando o modo raw-text da tag script."""

from __future__ import annotations

import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path


NODE = Path(
    r"C:\Users\daniel.laranjo\.cache\codex-runtimes\codex-primary-runtime"
    r"\dependencies\node\bin\node.exe"
)


class ScriptCollector(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.inside = False
        self.current = []
        self.scripts = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "script":
            self.inside = True
            self.current = []

    def handle_data(self, data):
        if self.inside:
            self.current.append(data)

    def handle_endtag(self, tag):
        if tag.lower() == "script" and self.inside:
            self.scripts.append("".join(self.current))
            self.current = []
            self.inside = False


def validate(path: Path) -> None:
    parser = ScriptCollector()
    parser.feed(path.read_text(encoding="utf-8"))
    if parser.inside:
        raise RuntimeError("Tag script não foi fechada corretamente.")
    for index, script in enumerate(parser.scripts, 1):
        result = subprocess.run(
            [str(NODE), "--check"],
            input=script.encode("utf-8"),
            capture_output=True,
        )
        if result.returncode:
            raise RuntimeError(
                f"Script {index} inválido: {result.stderr.decode('utf-8', errors='replace').strip()}"
            )
    print(f"HTML_JS_OK|{path}|scripts={len(parser.scripts)}")


if __name__ == "__main__":
    for argument in sys.argv[1:]:
        validate(Path(argument))
