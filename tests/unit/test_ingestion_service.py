import pytest

from app.core.exceptions import InvalidStatusTransitionError
from app.documents.ingestion import validate_status_transition
from app.documents.models import DocumentStatus


@pytest.mark.parametrize("current, target", [
    (DocumentStatus.PENDING, DocumentStatus.PROCESSING),
    (DocumentStatus.PENDING, DocumentStatus.FAILED),
    (DocumentStatus.PROCESSING, DocumentStatus.PROCESSED),
    (DocumentStatus.PROCESSING, DocumentStatus.FAILED),
    (DocumentStatus.FAILED, DocumentStatus.PENDING),
])
def test_valid_transitions(current, target):
    validate_status_transition(current, target)


@pytest.mark.parametrize("current, target", [
    (DocumentStatus.PROCESSED, DocumentStatus.PENDING),
    (DocumentStatus.PROCESSED, DocumentStatus.PROCESSING),
    (DocumentStatus.PROCESSED, DocumentStatus.FAILED),
    (DocumentStatus.PENDING, DocumentStatus.PROCESSED),
    (DocumentStatus.PROCESSING, DocumentStatus.PENDING),
])
def test_invalid_transitions(current, target):
    with pytest.raises(InvalidStatusTransitionError):
        validate_status_transition(current, target)


def test_processed_is_terminal():
    for target in DocumentStatus:
        if target != DocumentStatus.PROCESSED:
            with pytest.raises(InvalidStatusTransitionError):
                validate_status_transition(DocumentStatus.PROCESSED, target)
