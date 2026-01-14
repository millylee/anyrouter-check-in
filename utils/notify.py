import os
import smtplib
from email.mime.text import MIMEText
from typing import Literal

import httpx


class NotificationKit:
	def __init__(self):
		self.email_user: str = os.getenv('EMAIL_USER', '')
		self.email_pass: str = os.getenv('EMAIL_PASS', '')
		self.email_to: str = os.getenv('EMAIL_TO', '')
		self.email_sender: str = os.getenv('EMAIL_SENDER', '')
		self.smtp_server: str = os.getenv('CUSTOM_SMTP_SERVER', '')
		self.pushplus_token = os.getenv('PUSHPLUS_TOKEN')
		self.server_push_key = os.getenv('SERVERPUSHKEY')
		self.dingding_webhook = os.getenv('DINGDING_WEBHOOK')
		self.feishu_webhook = os.getenv('FEISHU_WEBHOOK')
		self.weixin_webhook = os.getenv('WEIXIN_WEBHOOK')
		self.gotify_url = os.getenv('GOTIFY_URL')
		self.gotify_token = os.getenv('GOTIFY_TOKEN')
		gotify_priority_env = os.getenv('GOTIFY_PRIORITY', '9')
		self.gotify_priority = int(gotify_priority_env) if gotify_priority_env.strip() else 9
		self.telegram_bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
		self.telegram_chat_id = os.getenv('TELEGRAM_CHAT_ID')
		self.bark_key = os.getenv('BARK_KEY')
		self.bark_server = os.getenv('BARK_SERVER', 'https://api.day.app')

	def send_email(self, title: str, content: str, msg_type: Literal['text', 'html'] = 'text'):
		if not self.email_user or not self.email_pass or not self.email_to:
			raise ValueError('Email configuration not set')

		# 如果未设置 EMAIL_SENDER，使用 EMAIL_USER 作为默认值
		sender = self.email_sender if self.email_sender else self.email_user

		# MIMEText 需要 'plain' 或 'html'，而不是 'text'
		mime_subtype = 'plain' if msg_type == 'text' else 'html'
		msg = MIMEText(content, mime_subtype, 'utf-8')
		msg['From'] = f'AnyRouter Assistant <{sender}>'
		msg['To'] = self.email_to
		msg['Subject'] = title

		smtp_server = self.smtp_server if self.smtp_server else f'smtp.{self.email_user.split("@")[1]}'
		with smtplib.SMTP_SSL(smtp_server, 465) as server:
			server.login(self.email_user, self.email_pass)
			server.send_message(msg)

	def send_pushplus(self, title: str, content: str):
		if not self.pushplus_token:
			raise ValueError('PushPlus Token not configured')

		data = {'token': self.pushplus_token, 'title': title, 'content': content, 'template': 'html'}
		with httpx.Client(timeout=30.0) as client:
			client.post('http://www.pushplus.plus/send', json=data)

	def send_serverPush(self, title: str, content: str):
		if not self.server_push_key:
			raise ValueError('Server Push key not configured')

		data = {'title': title, 'desp': content}
		with httpx.Client(timeout=30.0) as client:
			client.post(f'https://sctapi.ftqq.com/{self.server_push_key}.send', json=data)

	def send_dingtalk(self, title: str, content: str):
		if not self.dingding_webhook:
			raise ValueError('DingTalk Webhook not configured')

		data = {'msgtype': 'text', 'text': {'content': f'{title}\n{content}'}}
		with httpx.Client(timeout=30.0) as client:
			client.post(self.dingding_webhook, json=data)

	def send_feishu(self, title: str, content: str):
		if not self.feishu_webhook:
			raise ValueError('Feishu Webhook not configured')

		data = {
			'msg_type': 'interactive',
			'card': {
				'elements': [{'tag': 'markdown', 'content': content, 'text_align': 'left'}],
				'header': {'template': 'blue', 'title': {'content': title, 'tag': 'plain_text'}},
			},
		}
		with httpx.Client(timeout=30.0) as client:
			client.post(self.feishu_webhook, json=data)

	def send_wecom(self, title: str, content: str):
		if not self.weixin_webhook:
			raise ValueError('WeChat Work Webhook not configured')

		data = {'msgtype': 'text', 'text': {'content': f'{title}\n{content}'}}
		with httpx.Client(timeout=30.0) as client:
			client.post(self.weixin_webhook, json=data)

	def send_gotify(self, title: str, content: str):
		if not self.gotify_url or not self.gotify_token:
			raise ValueError('Gotify URL or Token not configured')

		# 使用环境变量配置的优先级，默认为9
		priority = self.gotify_priority

		# 确保优先级在有效范围内 (1-10)
		priority = max(1, min(10, priority))

		data = {
			'title': title,
			'message': content,
			'priority': priority
		}

		url = f'{self.gotify_url}?token={self.gotify_token}'
		with httpx.Client(timeout=30.0) as client:
			client.post(url, json=data)

	def send_telegram(self, title: str, content: str):
		if not self.telegram_bot_token or not self.telegram_chat_id:
			raise ValueError('Telegram Bot Token or Chat ID not configured')

		message = f'<b>{title}</b>\n\n{content}'
		data = {'chat_id': self.telegram_chat_id, 'text': message, 'parse_mode': 'HTML'}
		url = f'https://api.telegram.org/bot{self.telegram_bot_token}/sendMessage'
		with httpx.Client(timeout=30.0) as client:
			client.post(url, json=data)

	def send_bark(self, title: str, content: str):
		if not self.bark_key:
			raise ValueError('Bark Key not configured')

		# Bark API 支持 GET/POST，这里使用 POST JSON 方式支持更多参数
		# 文档: https://bark.day.app/#/tutorial
		url = f'{self.bark_server.rstrip("/")}/push'
		data = {
			'device_key': self.bark_key,
			'title': title,
			'body': content,
			'icon': 'https://anyrouter.top/favicon.ico',  # 可选：尝试使用 AnyRouter 图标
			'group': 'AnyRouter'
		}

		with httpx.Client(timeout=30.0) as client:
			client.post(url, json=data)

	def push_message(self, title: str, content: str, msg_type: Literal['text', 'html'] = 'text'):
		notifications = [
			('Email', lambda: self.send_email(title, content, msg_type)),
			('PushPlus', lambda: self.send_pushplus(title, content)),
			('Server Push', lambda: self.send_serverPush(title, content)),
			('DingTalk', lambda: self.send_dingtalk(title, content)),
			('Feishu', lambda: self.send_feishu(title, content)),
			('WeChat Work', lambda: self.send_wecom(title, content)),
			('Gotify', lambda: self.send_gotify(title, content)),
			('Telegram', lambda: self.send_telegram(title, content)),
			('Bark', lambda: self.send_bark(title, content)),
		]

		for name, func in notifications:
			try:
				func()
				print(f'[{name}]: Message push successful!')
			except Exception as e:
				print(f'[{name}]: Message push failed! Reason: {str(e)}')


notify = NotificationKit()
