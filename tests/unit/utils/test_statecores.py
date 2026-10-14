from salt.exceptions import CommandExecutionError

from saltext.github.utils.gh import statecores


def test_catch_errors_renders_failed_state():
    @statecores.catch_errors
    def _state(name):
        raise CommandExecutionError("damn")

    assert _state("mystate") == {
        "name": "mystate",
        "changes": {},
        "result": False,
        "comment": "damn",
    }


def test_catch_errors_reports_partial_changes():
    @statecores.catch_errors
    def _state(name):
        raise statecores.StateError("damn", changes={"created": "foo"})

    assert _state("mystate") == {
        "name": "mystate",
        "changes": {"created": "foo"},
        "result": False,
        "comment": "damn",
    }


def test_catch_errors_passes_through_success():
    ret = {"name": "mystate", "changes": {}, "result": True, "comment": "all good"}

    @statecores.catch_errors
    def _state(name, extra, *, kwarg=None):
        assert (name, extra, kwarg) == ("mystate", "pos", "kw")
        return ret

    assert _state("mystate", "pos", kwarg="kw") is ret
