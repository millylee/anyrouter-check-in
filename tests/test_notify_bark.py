import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from utils.notify import NotificationKit


@pytest.fixture
def bark_kit(monkeypatch):
	monkeypatch.setenv('BARK_KEY', 'test_bark_key')
	monkeypatch.delenv('BARK_SERVER', raising=False)
	return NotificationKit()


def test_send_bark_accepts_success_response(monkeypatch, bark_kit):
	response = MagicMock()
	response.json.return_value = {'code': 200, 'message': 'success'}

	client = MagicMock()
	client.post.return_value = response
	client_class = MagicMock()
	client_class.return_value.__enter__.return_value = client
	monkeypatch.setattr('utils.notify.httpx.Client', client_class)

	bark_kit.send_bark('title', 'content')

	response.raise_for_status.assert_called_once_with()
	client.post.assert_called_once()


def test_send_bark_rejects_error_response(monkeypatch, bark_kit):
	response = MagicMock()
	response.json.return_value = {'code': 400, 'message': 'invalid device key'}

	client = MagicMock()
	client.post.return_value = response
	client_class = MagicMock()
	client_class.return_value.__enter__.return_value = client
	monkeypatch.setattr('utils.notify.httpx.Client', client_class)

	with pytest.raises(ValueError, match='Bark API returned code 400: invalid device key'):
		bark_kit.send_bark('title', 'content')
