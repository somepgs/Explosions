import pytest

from tests.fixtures.sample_project import SampleNoteData, build_sample_note_data


@pytest.fixture
def sample_note_data() -> SampleNoteData:
    return build_sample_note_data()
