import json

from utils.config import AppConfig, ProviderConfig


def test_builtin_provider_profile_persistence_defaults(monkeypatch):
	monkeypatch.delenv('PROVIDERS', raising=False)

	config = AppConfig.load_from_env()

	assert config.providers['anyrouter'].persist_profile is True
	assert config.providers['agentrouter'].persist_profile is False


def test_provider_profile_persistence_can_override_builtin(monkeypatch):
	monkeypatch.setenv(
		'PROVIDERS',
		json.dumps(
			{
				'anyrouter': {'domain': 'https://anyrouter.top', 'persist_profile': False},
				'agentrouter': {'domain': 'https://agentrouter.org', 'persist_profile': True},
			}
		),
	)

	config = AppConfig.load_from_env()

	assert config.providers['anyrouter'].persist_profile is False
	assert config.providers['agentrouter'].persist_profile is True


def test_custom_provider_profile_persistence_defaults_to_false(monkeypatch):
	monkeypatch.setenv('PROVIDERS', json.dumps({'custom': {'domain': 'https://custom.example.com'}}))

	config = AppConfig.load_from_env()

	assert config.providers['custom'].persist_profile is False


def test_provider_from_dict_inherits_profile_persistence_from_defaults():
	defaults = ProviderConfig(name='custom', domain='https://old.example.com', persist_profile=True)

	provider = ProviderConfig.from_dict(
		'custom',
		{'domain': 'https://new.example.com'},
		defaults=defaults,
	)

	assert provider.persist_profile is True


def test_all_builtin_providers_default_to_proxy(monkeypatch):
	"""内置 provider 统一默认 use_proxy=True，避免逐个站点排查网络问题"""
	monkeypatch.delenv('PROVIDERS', raising=False)

	config = AppConfig.load_from_env()

	assert config.providers, 'builtin providers should not be empty'
	disabled = sorted(name for name, provider in config.providers.items() if not provider.use_proxy)
	assert disabled == []


def test_builtin_proxy_can_be_disabled_per_provider(monkeypatch):
	monkeypatch.setenv(
		'PROVIDERS',
		json.dumps({'anyrouter': {'domain': 'https://anyrouter.top', 'use_proxy': False}}),
	)

	config = AppConfig.load_from_env()

	assert config.providers['anyrouter'].use_proxy is False
	# 未覆盖的站点保持默认
	assert config.providers['seekai'].use_proxy is True


def test_custom_provider_proxy_defaults_to_false(monkeypatch):
	"""自定义 provider 仍默认不走代理，避免误连未配置的代理端口"""
	monkeypatch.setenv('PROVIDERS', json.dumps({'custom': {'domain': 'https://custom.example.com'}}))

	config = AppConfig.load_from_env()

	assert config.providers['custom'].use_proxy is False
