"""
Convert cookie.json to a single-line minified JSON string.

Usage:
	python config/convert_cookie.py
"""

import json
from pathlib import Path


def main():
	cookie_file = Path(__file__).parent / "cookie.json"
	if not cookie_file.exists():
		print(f"Error: {cookie_file} not found")
		return

	with open(cookie_file, "r", encoding="utf-8") as f:
		data = json.load(f)

	print()
	print(json.dumps(data, ensure_ascii=False, separators=(",", ":")))


if __name__ == "__main__":
	main()
