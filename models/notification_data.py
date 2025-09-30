from typing import List, Optional
from dataclasses import dataclass


@dataclass
class AccountResult:
    """单个账号的处理结果"""

    # 账号名称
    name: str

    # 处理状态：success 或 failed
    status: str

    # 当前余额，成功时才有
    quota: Optional[float] = None

    # 已使用余额，成功时才有
    used: Optional[float] = None

    # 错误信息，失败时才有
    error: Optional[str] = None


@dataclass
class NotificationStats:
    """通知统计信息"""

    # 成功数量
    success_count: int

    # 失败数量
    failed_count: int

    # 总数量
    total_count: int


@dataclass
class NotificationData:
    """通知数据结构"""

    # 账号列表和处理结果
    accounts: List[AccountResult]

    # 统计信息
    stats: NotificationStats

    # 执行时间戳
    timestamp: Optional[str] = None

    @property
    def all_success(self) -> bool:
        """是否全部成功"""
        return self.stats.failed_count == 0

    @property
    def all_failed(self) -> bool:
        """是否全部失败"""
        return self.stats.success_count == 0

    @property
    def partial_success(self) -> bool:
        """是否部分成功"""
        return self.stats.success_count > 0 and self.stats.failed_count > 0
