from app import config
from app.models import WiderspruchWorkflowRequest


def test_config_defaults():
    assert config.DEFAULT_K >= 1
    assert config.COLLECTION
    assert config.APP_URL.startswith("http")


def test_workflow_model_defaults():
    req = WiderspruchWorkflowRequest(user_id="x", text="hello")
    assert req.preview is False
    assert req.format == "txt"
