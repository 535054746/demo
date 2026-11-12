from typing import Literal
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class ComplaintRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    ticket_no: str = Field(
        min_length=1,
        max_length=64,
        description="工单号",
    )
    channel: Literal["site_message", "email"]

    order_no: str = Field(
        min_length=1,
        max_length=64,
        description="订单号",
    )

    tracking_no: str | None = Field(
        default=None,
        min_length=1,
        max_length=64,
        description="物流单号",
    )

    content: str = Field(
        min_length=1,
        max_length=1024,
        description="投诉内容",
    )



class ComplaintConfirmRequest(BaseModel):
    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
    )

    confirmed: Literal[True]
    operator: str = Field(min_length=1, max_length=64)

    action: Literal[
        "follow_up",  # 继续跟进
        "goodwill",   # 挽留补偿
        "refund",     # 退款
        "reship",     # 补发
    ]

    amount: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        max_digits=10,
        decimal_places=2,
    )

    tracking_no: str | None = Field(
        default=None,
        min_length=1,
        max_length=64,
    )

    note: str = Field(min_length=1, max_length=1000)


class ComplaintCloseRequest(BaseModel):
    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
    )

    operator: str = Field(min_length=1, max_length=64)
    outcome: str = Field(min_length=1, max_length=1000)
    improvement: str = Field(min_length=1, max_length=1000)