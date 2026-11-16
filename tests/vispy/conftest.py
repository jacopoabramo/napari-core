"""Fixtures of the vispy backend tests."""

from collections.abc import Generator

import pytest
from PyQt6.QtCore import QCoreApplication, QEvent
from vispy.app import Application


@pytest.fixture(autouse=True)
def delete_closed_widgets(qapp: Application) -> Generator[None, None, None]:
    """Have Qt delete the widgets that the test scheduled for deletion."""
    yield
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete.value)
