import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
for _path in (PROJECT_ROOT, PROJECT_ROOT / "src"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from explosions_core.io.project_file import save_project_file  # noqa: E402
from tests.fixtures.sample_project import build_sample_project_definition  # noqa: E402

OUTPUT_FILE = PROJECT_ROOT / "examples" / "demo_project.json"


def main() -> None:
    path = save_project_file(build_sample_project_definition(), OUTPUT_FILE)
    print(f"Сохранено: {path}")


if __name__ == "__main__":
    main()
