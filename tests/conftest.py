import pytest

from futdados.db import Repository


@pytest.fixture
def repo():
    r = Repository(":memory:")
    yield r
    r.close()
