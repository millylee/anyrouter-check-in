import os
import smtplib
from email.mime.text import MIMEText
from typing import Literal

import httpx
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()


class NotificationKit:
	def __init__(self):
		self.email_user: str = os.getenv('EMAIL_USER', '')
		self.email_pass: str = os.getenv('EMAIL_PASS', '')
		self.email_to: str = os.getenv('EMAIL_TO', '')
		self.smtp_server: str = os.getenv('CUSTOM_SMTP_SERVER', '')
		self.pushplus_token = os.getenv('PUSHPLUS_TOKEN')
		self.server_push_key = os.getenv('SERVERPUSHKEY')
		self.dingding_webhook = os.getenv('DINGDING_WEBHOOK')
		self.feishu_webhook = os.getenv('FEISHU_WEBHOOK')
		self.weixin_webhook = os.getenv('WEIXIN_WEBHOOK')

	def send_email(self, title: str, content: str, msg_type: Literal['text', 'html'] = 'text'):
		if not self.email_user or not self.email_pass or not self.email_to:
			raise ValueError('邮箱配置未设置')

		# MIMEText 需要 'plain' 或 'html'，而不是 'text'
		mime_subtype = 'plain' if msg_type == 'text' else 'html'
		msg = MIMEText(content, mime_subtype, 'utf-8')
		msg['From'] = f'AnyRouter Assistant <{self.email_user}>'
		msg['To'] = self.email_to
		msg['Subject'] = title

		smtp_server = self.smtp_server if self.smtp_server else f'smtp.{self.email_user.split("@")[1]}'
		with smtplib.SMTP_SSL(smtp_server, 465) as server:
			server.login(self.email_user, self.email_pass)
			server.send_message(msg)

	def send_pushplus(self, title: str, content: str):
		if not self.pushplus_token:
			raise ValueError('PushPlus Token 未配置')

		data = {'token': self.pushplus_token, 'title': title, 'content': content, 'template': 'html'}
		with httpx.Client(timeout=30.0) as client:
			client.post('http://www.pushplus.plus/send', json=data)

	def send_serverPush(self, title: str, content: str):
		if not self.server_push_key:
			raise ValueError('Server酱 SendKey 未配置')

		data = {'title': title, 'desp': content}
		with httpx.Client(timeout=30.0) as client:
			client.post(f'https://sctapi.ftqq.com/{self.server_push_key}.send', json=data)

	def send_dingtalk(self, title: str, content: str):
		if not self.dingding_webhook:
			raise ValueError('钉钉 Webhook 未配置')

		data = {'msgtype': 'text', 'text': {'content': f'{title}\n{content}'}}
		with httpx.Client(timeout=30.0) as client:
			client.post(self.dingding_webhook, json=data)

	def send_feishu(self, title: str, content: str):
		if not self.feishu_webhook:
			raise ValueError('飞书 Webhook 未配置')

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
			raise ValueError('企业微信 Webhook 未配置')

		data = {'msgtype': 'text', 'text': {'content': f'{title}\n{content}'}}
		with httpx.Client(timeout=30.0) as client:
			client.post(self.weixin_webhook, json=data)

	def push_message(self, title: str, content: str, msg_type: Literal['text', 'html'] = 'text'):
		notifications = [
			('📧 邮箱', lambda: self.send_email(title, content, msg_type)),
			('📱 PushPlus', lambda: self.send_pushplus(title, content)),
			('🔔 Server酱', lambda: self.send_serverPush(title, content)),
			('💬 钉钉', lambda: self.send_dingtalk(title, content)),
			('📲 飞书', lambda: self.send_feishu(title, content)),
			('💼 企业微信', lambda: self.send_wecom(title, content)),
		]

		for name, func in notifications:
			try:
				func()
				print(f'{name}: 消息推送成功！')
			except Exception as e:
				print(f'{name}: 消息推送失败！原因: {str(e)}')


notify = NotificationKit()
