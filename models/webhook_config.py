from typing import Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class WebhookConfig:
    """Webhook 配置参数类"""

    # Webhook URL 地址
    webhook: str

    # 平台设置，比如 use_card、color_theme 等
    platform_settings: Optional[Dict[str, Any]] = None

    # 模板内容，如果为空则使用默认模板
    template: Optional[str] = None
