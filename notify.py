import json
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Dict, Any, Optional, Literal, Union

import httpx
import stencil

from models import (
	EmailConfig,
	WebhookConfig,
	PushPlusConfig,
	ServerPushConfig,
	NotificationData,
)


class NotificationKit:
	def __init__(self):
		# 配置文件路径
		self.config_dir = Path(__file__).parent / 'notif_config'

		# 加载各平台配置
		self.email_config = self._load_email_config()
		self.dingtalk_config = self._load_dingtalk_config()
		self.feishu_config = self._load_feishu_config()
		self.wecom_config = self._load_wecom_config()
		self.pushplus_config = self._load_pushplus_config()
		self.serverpush_config = self._load_serverpush_config()

	def send_email(self, title: str, content: str, msg_type: Literal['text', 'html'] = 'text'):
		if not self.email_config:
			raise ValueError('未配置邮箱信息')

		msg = MIMEMultipart()
		msg['From'] = f'AnyRouter Assistant <{self.email_config.user}>'
		msg['To'] = self.email_config.to
		msg['Subject'] = title

		body = MIMEText(content, msg_type, 'utf-8')
		msg.attach(body)

		smtp_server = self.email_config.smtp_server if self.email_config.smtp_server else f'smtp.{self.email_config.user.split("@")[1]}'
		with smtplib.SMTP_SSL(smtp_server, 465) as server:
			server.login(self.email_config.user, self.email_config.password)
			server.send_message(msg)

	def send_pushplus(self, title: str, content: str):
		if not self.pushplus_config:
			raise ValueError('未配置PushPlus Token')

		data = {
			'token': self.pushplus_config.token,
			'title': title,
			'content': content,
			'template': 'html'
		}
		with httpx.Client(timeout=30.0) as client:
			client.post('http://www.pushplus.plus/send', json=data)

	def send_serverpush(self, title: str, content: str):
		if not self.serverpush_config:
			raise ValueError('未配置Server Push key')

		data = {'title': title, 'desp': content}
		with httpx.Client(timeout=30.0) as client:
			client.post(f'https://sctapi.ftqq.com/{self.serverpush_config.send_key}.send', json=data)

	def send_dingtalk(self, title: str, content: str):
		if not self.dingtalk_config:
			raise ValueError('未配置钉钉 Webhook')

		data = {'msgtype': 'text', 'text': {'content': f'{title}\n{content}'}}
		with httpx.Client(timeout=30.0) as client:
			client.post(self.dingtalk_config.webhook, json=data)

	def send_feishu(self, title: str, content: str):
		if not self.feishu_config:
			raise ValueError('未配置飞书 Webhook')

		# 检查是否使用卡片模式（确保 platform_settings 不为 None）
		platform_settings = self.feishu_config.platform_settings or {}
		use_card = platform_settings.get('use_card', True)
		color_theme = platform_settings.get('color_theme', 'blue')

		if use_card:
			data = {
				'msg_type': 'interactive',
				'card': {
					'elements': [{'tag': 'markdown', 'content': content, 'text_align': 'left'}],
					'header': {'template': color_theme, 'title': {'content': title, 'tag': 'plain_text'}},
				},
			}
		else:
			data = {'msg_type': 'text', 'text': {'content': f'{title}\n{content}'}}

		with httpx.Client(timeout=30.0) as client:
			client.post(self.feishu_config.webhook, json=data)

	def send_wecom(self, title: str, content: str):
		if not self.wecom_config:
			raise ValueError('未配置企业微信 Webhook')

		# 检查 markdown_style 配置（确保 platform_settings 不为 None）
		platform_settings = self.wecom_config.platform_settings or {}
		markdown_style = platform_settings.get('markdown_style', 'markdown')

		# 根据 markdown_style 选择消息格式
		# 如果 markdown_style 包含 'markdown'，则直接作为消息类型；否则使用 text 模式
		if markdown_style and 'markdown' in str(markdown_style):
			data = {'msgtype': markdown_style, markdown_style: {'content': f'**{title}**\n{content}'}}
		else:
			data = {'msgtype': 'text', 'text': {'content': f'{title}\n{content}'}}

		with httpx.Client(timeout=30.0) as client:
			client.post(self.wecom_config.webhook, json=data)

	def push_message(self, title: str, content: Union[str, NotificationData], msg_type: Literal['text', 'html'] = 'text'):
		"""发送通知消息

		Args:
			title: 消息标题
			content: 消息内容，可以是字符串（向后兼容）或 NotificationData 结构
			msg_type: 消息类型
		"""
		notifications = [
			('邮箱', self._send_email_with_template),
			('PushPlus', self._send_pushplus_with_template),
			('Server 酱', self._send_serverpush_with_template),
			('钉钉', self._send_dingtalk_with_template),
			('飞书', self._send_feishu_with_template),
			('企业微信', self._send_wecom_with_template),
		]

		for name, func in notifications:
			try:
				func(title, content, msg_type)
				print(f'[{name}]: Message push successful!')
			except Exception as e:
				print(f'[{name}]: Message push failed! Reason: {str(e)}')


	# 配置加载方法
	def _load_default_config(self, platform: str) -> Optional[Dict[str, Any]]:
		"""加载默认配置文件"""
		config_file = self.config_dir / f'{platform}.json'
		if config_file.exists():
			try:
				with open(config_file, 'r', encoding='utf-8') as f:
					return json.load(f)
			except Exception as e:
				print(f'Warning: Failed to load default config file {config_file}: {e}')
		return None

	def _parse_env_config(self, env_value: str) -> Union[str, Dict[str, Any]]:
		"""解析环境变量配置"""
		try:
			# 尝试解析为 JSON
			return json.loads(env_value)
		except json.JSONDecodeError:
			# 如果不是 JSON，就当做纯字符串（Token 或 Webhook URL）
			return env_value

	def _load_email_config(self) -> Optional[EmailConfig]:
		"""加载邮箱配置"""
		# 检查新的配置方式
		email_notif_config = os.getenv('EMAIL_NOTIF_CONFIG')
		if email_notif_config:
			parsed = self._parse_env_config(email_notif_config)
			if isinstance(parsed, dict):
				# 如果 template 为 None，则使用默认模板
				template = parsed.get('template')
				if template is None:
					default_config = self._load_default_config('email')
					template = default_config.get('template') if default_config else None

				return EmailConfig(
					user=parsed['user'],
					password=parsed['pass'],
					to=parsed['to'],
					smtp_server=parsed.get('smtp_server'),
					platform_settings=parsed.get('platform_settings'),
					template=template
				)

		# 检查旧的配置方式
		email_user = os.getenv('EMAIL_USER')
		email_pass = os.getenv('EMAIL_PASS')
		email_to = os.getenv('EMAIL_TO')
		custom_smtp = os.getenv('CUSTOM_SMTP_SERVER')

		if email_user and email_pass and email_to:
			# 加载默认模板
			default_config = self._load_default_config('email')
			return EmailConfig(
				user=email_user,
				password=email_pass,
				to=email_to,
				smtp_server=custom_smtp,
				platform_settings=default_config.get('platform_settings') if default_config else None,
				template=default_config.get('template') if default_config else None
			)

		return None

	def _load_webhook_config(self, platform: str, env_key: str, notif_config_key: str) -> Optional[WebhookConfig]:
		"""加载 Webhook 配置的通用方法"""
		# 检查新的配置方式
		notif_config = os.getenv(notif_config_key)
		if notif_config:
			parsed = self._parse_env_config(notif_config)
			if isinstance(parsed, dict):
				# 如果 template 为 None，则使用默认模板
				template = parsed.get('template')
				if template is None:
					default_config = self._load_default_config(platform)
					template = default_config.get('template') if default_config else None

				return WebhookConfig(
					webhook=parsed['webhook'],
					platform_settings=parsed.get('platform_settings'),
					template=template
				)
			else:
				# 纯字符串，当做 webhook URL，使用默认模板
				default_config = self._load_default_config(platform)
				return WebhookConfig(
					webhook=parsed,
					platform_settings=default_config.get('platform_settings') if default_config else None,
					template=default_config.get('template') if default_config else None
				)

		# 检查旧的配置方式
		old_webhook = os.getenv(env_key)
		if old_webhook:
			default_config = self._load_default_config(platform)
			return WebhookConfig(
				webhook=old_webhook,
				platform_settings=default_config.get('platform_settings') if default_config else None,
				template=default_config.get('template') if default_config else None
			)

		return None

	def _load_dingtalk_config(self) -> Optional[WebhookConfig]:
		return self._load_webhook_config('dingtalk', 'DINGDING_WEBHOOK', 'DINGTALK_NOTIF_CONFIG')

	def _load_feishu_config(self) -> Optional[WebhookConfig]:
		return self._load_webhook_config('feishu', 'FEISHU_WEBHOOK', 'FEISHU_NOTIF_CONFIG')

	def _load_wecom_config(self) -> Optional[WebhookConfig]:
		return self._load_webhook_config('wecom', 'WEIXIN_WEBHOOK', 'WECOM_NOTIF_CONFIG')

	def _load_pushplus_config(self) -> Optional[PushPlusConfig]:
		"""加载 PushPlus 配置"""
		# 检查新的配置方式
		pushplus_notif_config = os.getenv('PUSHPLUS_NOTIF_CONFIG')
		if pushplus_notif_config:
			parsed = self._parse_env_config(pushplus_notif_config)
			if isinstance(parsed, dict):
				# 如果 template 为 None，则使用默认模板
				template = parsed.get('template')
				if template is None:
					default_config = self._load_default_config('pushplus')
					template = default_config.get('template') if default_config else None

				return PushPlusConfig(
					token=parsed['token'],
					platform_settings=parsed.get('platform_settings'),
					template=template
				)
			else:
				# 纯字符串，当做 token，使用默认模板
				default_config = self._load_default_config('pushplus')
				return PushPlusConfig(
					token=parsed,
					platform_settings=default_config.get('platform_settings') if default_config else None,
					template=default_config.get('template') if default_config else None
				)

		# 检查旧的配置方式
		pushplus_token = os.getenv('PUSHPLUS_TOKEN')
		if pushplus_token:
			default_config = self._load_default_config('pushplus')
			return PushPlusConfig(
				token=pushplus_token,
				platform_settings=default_config.get('platform_settings') if default_config else None,
				template=default_config.get('template') if default_config else None
			)

		return None

	def _load_serverpush_config(self) -> Optional[ServerPushConfig]:
		"""加载 Server 酱配置"""
		# 检查新的配置方式
		serverpush_notif_config = os.getenv('SERVERPUSH_NOTIF_CONFIG')
		if serverpush_notif_config:
			parsed = self._parse_env_config(serverpush_notif_config)
			if isinstance(parsed, dict):
				# 如果 template 为 None，则使用默认模板
				template = parsed.get('template')
				if template is None:
					default_config = self._load_default_config('serverpush')
					template = default_config.get('template') if default_config else None

				return ServerPushConfig(
					send_key=parsed['send_key'],
					platform_settings=parsed.get('platform_settings'),
					template=template
				)
			else:
				# 纯字符串，当做 send_key，使用默认模板
				default_config = self._load_default_config('serverpush')
				return ServerPushConfig(
					send_key=parsed,
					platform_settings=default_config.get('platform_settings') if default_config else None,
					template=default_config.get('template') if default_config else None
				)

		# 检查旧的配置方式
		server_push_key = os.getenv('SERVERPUSHKEY')
		if server_push_key:
			default_config = self._load_default_config('serverpush')
			return ServerPushConfig(
				send_key=server_push_key,
				platform_settings=default_config.get('platform_settings') if default_config else None,
				template=default_config.get('template') if default_config else None
			)

		return None

	# 模板渲染方法
	def _render_template(self, template: str, data: NotificationData) -> str:
		"""渲染模板

		注意: Stencil 模板引擎有以下限制:
		1. 不支持比较操作符 (==, !=, <, > 等)
		2. 不支持字典的点访问，只能访问对象属性
		因此我们提供分组的账号列表和对象形式的数据
		"""
		try:
			# 分组账号（因为 Stencil 不支持 == 比较）
			success_accounts = [acc for acc in data.accounts if acc.status == 'success']
			failed_accounts = [acc for acc in data.accounts if acc.status != 'success']

			context_data = {
				'timestamp': data.timestamp,
				'stats': data.stats,  # dataclass 对象，支持 {{ stats.success_count }}

				# 提供分组的账号列表（AccountResult 对象）
				'success_accounts': success_accounts,
				'failed_accounts': failed_accounts,

				# 保留完整列表供需要的模板使用
				'accounts': data.accounts,  # AccountResult 对象列表

				# 便利变量：布尔标志
				'has_success': len(success_accounts) > 0,
				'has_failed': len(failed_accounts) > 0,
				'all_success': len(failed_accounts) == 0,
				'all_failed': len(success_accounts) == 0,
				'partial_success': len(success_accounts) > 0 and len(failed_accounts) > 0,
			}

			# 解析并渲染模板
			template_obj = stencil.Template(template)
			context = stencil.Context(context_data)
			rendered_result = template_obj.render(context)

			# 处理换行符：将 \\n 转换为真正的换行符
			rendered_result = rendered_result.replace('\\n', '\n')

			return rendered_result
		except Exception as e:
			print(f'ERROR: Template rendering failed: {e}')
			# 如果模板渲染失败，返回简单格式
			return f'{data.timestamp}\n\n' + '\n\n'.join([
				f'[{"SUCCESS" if account.status == "success" else "FAIL"}] {account.name}'
				for account in data.accounts
			])

	# 带模板的发送方法
	def _send_email_with_template(self, title: str, content: Union[str, NotificationData], msg_type: Literal['text', 'html'] = 'text'):
		if not self.email_config:
			return

		if isinstance(content, NotificationData) and self.email_config.template:
			rendered_content = self._render_template(self.email_config.template, content)
		else:
			rendered_content = str(content)

		self.send_email(title, rendered_content, msg_type)

	def _send_pushplus_with_template(self, title: str, content: Union[str, NotificationData], msg_type: Literal['text', 'html'] = 'text'):
		if not self.pushplus_config:
			return

		if isinstance(content, NotificationData) and self.pushplus_config.template:
			rendered_content = self._render_template(self.pushplus_config.template, content)
		else:
			rendered_content = str(content)

		self.send_pushplus(title, rendered_content)

	def _send_serverpush_with_template(self, title: str, content: Union[str, NotificationData], msg_type: Literal['text', 'html'] = 'text'):
		if not self.serverpush_config:
			return

		if isinstance(content, NotificationData) and self.serverpush_config.template:
			rendered_content = self._render_template(self.serverpush_config.template, content)
		else:
			rendered_content = str(content)

		self.send_serverpush(title, rendered_content)

	def _send_dingtalk_with_template(self, title: str, content: Union[str, NotificationData], msg_type: Literal['text', 'html'] = 'text'):
		if not self.dingtalk_config:
			return

		if isinstance(content, NotificationData) and self.dingtalk_config.template:
			rendered_content = self._render_template(self.dingtalk_config.template, content)
		else:
			rendered_content = str(content)

		self.send_dingtalk(title, rendered_content)

	def _send_feishu_with_template(self, title: str, content: Union[str, NotificationData], msg_type: Literal['text', 'html'] = 'text'):
		if not self.feishu_config:
			return

		if isinstance(content, NotificationData) and self.feishu_config.template:
			rendered_content = self._render_template(self.feishu_config.template, content)
		else:
			rendered_content = str(content)

		self.send_feishu(title, rendered_content)

	def _send_wecom_with_template(self, title: str, content: Union[str, NotificationData], msg_type: Literal['text', 'html'] = 'text'):
		if not self.wecom_config:
			return

		if isinstance(content, NotificationData) and self.wecom_config.template:
			rendered_content = self._render_template(self.wecom_config.template, content)
		else:
			rendered_content = str(content)

		self.send_wecom(title, rendered_content)


notify = NotificationKit()
