from pydantic import BaseModel, Field, ConfigDict

class TrackingQueryRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    order_no: str | None = Field(default=None,min_length=1, max_length=64, description="订单号")
    tracking_no: str | None = Field(default=None,min_length=1, max_length=64, description="物流单号")
    question: str = Field(min_length=1, max_length=1024, description="客户咨询内容")


