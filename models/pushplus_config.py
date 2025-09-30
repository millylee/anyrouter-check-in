from typing import Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class PushPlusConfig:
    """PushPlus 配置参数类"""

    # PushPlus Token
    token: str

    # 平台设置
    platform_settings: Optional[Dict[str, Any]] = None

    # 模板内容，如果为空则使用默认模板
    template: Optional[str] = None
