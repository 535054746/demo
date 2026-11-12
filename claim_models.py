from typing import Literal
from pydantic import BaseModel, Field, ConfigDict

class ClaimRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    order_no: str = Field(min_length=1, max_length=64, description="订单号")
    tracking_no: str | None = Field(default=None,min_length=1, max_length=64, description="物流单号")

    source: Literal["order_team", "customer"] = Field(description="来源")

    problem_type: Literal[
        "tracking_stalled",  # 长期没有更新
        "delivered_not_received", # 显示送成功但未收到
        "damaged", # 显示已收到但物品损坏
        "other", # 其他
    ] = Field(description="问题类型")

    description: str = Field(min_length=1, max_length=1024, description="问题描述")



class ClaimConfirmRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    confirmed: Literal[True] = Field(description="客服确认执行，必须要True")

    operator: str = Field(
        min_length=1,
        max_length=64,
        description="操作人，可以是客服，也可以是业务员"
    )