"""Copy spec character cards to the integration characters directory, fixing YAML issues."""

import re
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).parent.parent
SPEC_DIR = REPO_ROOT / ".claude" / "spec"
OUT_DIR = REPO_ROOT / "custom_components" / "voiceforge" / "characters"


def fix_yaml_text(text: str) -> str:
    # Some spec entries have inline em-dash annotations after quoted strings:
    #   - "Of course" — too servile
    # This is invalid YAML. Strip everything after the em-dash on those lines.
    text = re.sub(r'(^\s*- "[^"]+") —[^\n]*', r"\1", text, flags=re.MULTILINE)
    text = re.sub(r"(^\s*- '[^']+') —[^\n]*", r"\1", text, flags=re.MULTILINE)
    return text


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for name in ["aria", "sera", "malachar", "shepherd"]:
        src = SPEC_DIR / f"{name}.yaml"
        raw_text = fix_yaml_text(src.read_text(encoding="utf-8"))
        data = yaml.safe_load(raw_text)
        data.get("memory", {}).pop("auto_summarize", None)
        out = OUT_DIR / f"{name}.yaml"
        out.write_text(
            yaml.dump(data, allow_unicode=True, default_flow_style=False, sort_keys=False),
            encoding="utf-8",
        )
        print(f"wrote {out.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
