from tests.support.github.routes.meta import RATE_LIMIT_RESOURCES


def test_rate_limit(github):
    ret = github.rate_limit()
    assert ret == RATE_LIMIT_RESOURCES
    # The deprecated top-level "rate" alias is not included
    assert "rate" not in ret
    assert "resources" not in ret
