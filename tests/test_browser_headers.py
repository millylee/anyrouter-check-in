from utils.headers import get_browser_headers, DEFAULT_USER_AGENT


def test_get_browser_headers_default():
	headers = get_browser_headers()
	assert "User-Agent" in headers
	assert "sec-ch-ua" in headers
	assert "sec-ch-ua-mobile" in headers
	assert "sec-ch-ua-platform" in headers
	assert headers["sec-ch-ua-mobile"] == "?0"
	assert "zh-CN" in headers["Accept-Language"]
	assert headers["User-Agent"] == DEFAULT_USER_AGENT


def test_get_browser_headers_with_domain():
	domain = "https://agentrouter.org"
	headers = get_browser_headers(domain=domain)
	assert headers["Origin"] == domain
	assert headers["Referer"] == f"{domain}/"


def test_get_browser_headers_with_extra():
	headers = get_browser_headers(extra={"X-Custom": "custom-val", "new-api-user": "12345"})
	assert headers["X-Custom"] == "custom-val"
	assert headers["new-api-user"] == "12345"
