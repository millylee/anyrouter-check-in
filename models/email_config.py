from typing import Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class EmailConfig:
    """邮件配置参数类"""

    # 发件人邮箱地址
    user: str

    # 发件人邮箱密码或授权码
    password: str

    # 收件人邮箱地址
    to: str

    # 自定义 SMTP 服务器地址（可选），如果不指定则自动从邮箱地址推断
    smtp_server: Optional[str] = None

    # 平台设置
    platform_settings: Optional[Dict[str, Any]] = None

    # 模板内容，如果为空则使用默认模板
    template: Optional[str] = None
