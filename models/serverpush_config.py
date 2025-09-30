from typing import Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class ServerPushConfig:
    """Server 酱配置参数类"""

    # Server 酱 SendKey
    send_key: str

    # 平台设置
    platform_settings: Optional[Dict[str, Any]] = None

    # 模板内容，如果为空则使用默认模板
    template: Optional[str] = None
