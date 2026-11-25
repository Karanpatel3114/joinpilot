from joinpilot.errors import JoinPilotError, NotFoundError, PayloadTooLargeError


def test_domain_errors_carry_code_status_and_details() -> None:
    error = NotFoundError("Project not found", {"project_id": "abc"})
    assert isinstance(error, JoinPilotError)
    assert error.code == "NOT_FOUND"
    assert error.http_status == 404
    assert error.message == "Project not found"
    assert error.details == {"project_id": "abc"}


def test_details_default_to_an_empty_dict() -> None:
    assert PayloadTooLargeError("too big").details == {}
