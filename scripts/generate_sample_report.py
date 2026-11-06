import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
for _path in (PROJECT_ROOT, PROJECT_ROOT / "src"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from explosions_core.export.reports.explanatory_note_docx import export_explanatory_note_docx  # noqa: E402
from tests.fixtures.sample_project import build_sample_note_data  # noqa: E402

OUTPUT_DIR = PROJECT_ROOT / "output_reports"
OUTPUT_FILE = OUTPUT_DIR / "Пояснительная_записка_Склад_ВМ_РК.docx"


def main() -> None:
    data = build_sample_note_data()
    path = export_explanatory_note_docx(
        data.project,
        data.sizing_records,
        data.detonation_results,
        data.uvv_results,
        data.berm_records,
        data.lightning_records,
        OUTPUT_FILE,
    )
    print(f"Сохранено: {path}")


if __name__ == "__main__":
    main()
