
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4
from complaint.complaint_models import (
    ComplaintConfirmRequest,
    ComplaintCloseRequest
)
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy import (
    JSON,
    String,
    UniqueConstraint,
    select,
    update,
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
)

from claim_store import Base, engine, SessionLocal
from complaint.complaint_tools import (
    query_complaint_order,
    query_complaint_policy
)
from complaint.complaint_models import (
    ComplaintCloseRequest,
    ComplaintRequest,
    ComplaintConfirmRequest
)


class ComplaintRecord(Base):
    __tablename__ = "complaints" 
    __table_args__ = (
        UniqueConstraint("user_id", "channel", "ticket_no"),
    )
    complaint_id: Mapped[str] = mapped_column(
        String(40),
        primary_key=True,
    )

    user_id: Mapped[str] = mapped_column(String(64))
    channel: Mapped[str] = mapped_column(String(16))
    ticket_no: Mapped[str] = mapped_column(String(64))

    request_json: Mapped[dict] = mapped_column(JSON)
    analysis_json: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(32))

    execution: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
    )
    review: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
    )

Base.metadata.create_all(engine)


def to_record(record: ComplaintRecord) -> dict:
    return {
        "complaint_id": record.complaint_id,
        "ticket_no": record.ticket_no,
        "channel": record.channel,
        "request": record.request_json,
        "analysis": record.analysis_json,
        "status": record.status,
        "execution": record.execution,
        "review": record.review,
    }

def _load(
    session,
    complaint_id: str,
    user_id: str
) -> ComplaintRecord:
    record = session.get(ComplaintRecord, complaint_id)
    if record is None or record.user_id != user_id:
        raise LookupError("未找到当前用户的客诉记录")

    return record


def _transition(
    session,
    record,
    expected: str,
    target: str,
    **values,
) -> dict:
    # 只有当前状态符合预期，才能进入下一状态。
    result = session.execute(
        update(ComplaintRecord)
        .where(
            ComplaintRecord.complaint_id == record.complaint_id,
            ComplaintRecord.status == expected,
        )
        .values(status=target, **values)
    )

    if result.rowcount != 1:
        raise ValueError("工单状态已变化，请重新查询")

    session.refresh(record)
    return to_record(record)


def save_complaint(
    request: ComplaintRequest,
    user_id: str,
    analysis: dict,
) -> dict:
    context = query_complaint_order(
        user_id,
        request.order_no,
        request.tracking_no,
    )

    if "error" in context:
        raise LookupError(context["error"])

    payload = request.model_dump(mode="json")

    with SessionLocal.begin() as session:
        session.execute(
            insert(ComplaintRecord)
            .values(
                complaint_id=f"COMP-{uuid4().hex}",
                user_id=user_id,
                channel=request.channel,
                ticket_no=request.ticket_no,
                request_json=payload,
                analysis_json=analysis,
                status="pending_review",
            )
            .on_conflict_do_nothing(
                index_elements=["user_id", "channel", "ticket_no"],
            )
        )

        record = session.scalar(
            select(ComplaintRecord).where(
                ComplaintRecord.user_id == user_id,
                ComplaintRecord.channel == request.channel,
                ComplaintRecord.ticket_no == request.ticket_no,
            )
        )

        if record.request_json != payload:
            raise ValueError(
                "该工单号已存在，但内容不同，请使用新的工单号"
            )

        return to_record(record)


def get_complaint(
    complaint_id: str,
    user_id: str,
) -> dict:
    with SessionLocal() as session:
        return to_record(_load(session, complaint_id, user_id))


def confirm_complaint(
    complaint_id: str,
    user_id: str,
    request: ComplaintConfirmRequest,
) -> dict:
    payload = request.model_dump(mode="json")

    with SessionLocal.begin() as session:
        record = _load(session, complaint_id, user_id)

        # 相同方案重复提交，返回原执行结果。
        if record.execution is not None:
            if record.execution["request"] == payload:
                return to_record(record)
            raise ValueError("已执行的方案不能重复更改")

        if record.status != "pending_review":
            raise ValueError("只有待审核工单可以确认")

        original = record.request_json

        if (
            original["tracking_no"] is not None
            and request.tracking_no is not None
            and request.tracking_no != original["tracking_no"]
        ):
            raise ValueError("不能更换本次投诉的运单")

        tracking_no = request.tracking_no or original["tracking_no"]

        context = query_complaint_order(
            user_id,
            original["order_no"],
            tracking_no,
        )

        if "error" in context:
            raise ValueError(context["error"])

        parcels = context["tracking"]

        if request.action != "follow_up":
            if len(parcels) != 1 or "error" in parcels[0]:
                raise ValueError(
                    "请先明确一个运单，并核实物流资料"
                )

        currency = None

        if request.action in ("goodwill", "refund"):
            policy = query_complaint_policy(
                user_id,
                original["order_no"],
            )

            if "error" in policy:
                raise ValueError(policy["error"])

            # 挽留补偿按规则上限；退款按订单实付金额上限。
            limit = (
                policy["goodwill_cap"]
                if request.action == "goodwill"
                else policy["order_details"]["paid_amount"]
            )

            if not Decimal("0") < request.amount <= Decimal(str(limit)):
                raise ValueError(
                    f"金额必须大于 0 且不得超过 {limit}"
                )

            currency = policy["currency"]

        elif request.amount != 0:
            raise ValueError("跟进或补发的 amount 必须为 0")

        execution = {
            "mode": "mock",
            "execution_no": f"MOCK-CP-{uuid4().hex[:12]}",
            "executed_at": datetime.now(timezone.utc).isoformat(),
            "tracking_no": tracking_no or (
                parcels[0].get("tracking_no")
                if len(parcels) == 1
                else None
            ),
            "currency": currency,
            "request": payload,
        }

        return _transition(
            session,
            record,
            "pending_review",
            "executed_mock",
            execution=execution,
        )


def close_complaint(
    complaint_id: str,
    user_id: str,
    request: ComplaintCloseRequest,
) -> dict:
    payload = request.model_dump(mode="json")

    with SessionLocal.begin() as session:
        record = _load(session, complaint_id, user_id)

        if record.review is not None:
            if record.review["request"] == payload:
                return to_record(record)
            raise ValueError("工单已结案，不能覆盖复盘")

        if record.status != "executed_mock":
            raise ValueError(
                "请先确认并完成模拟执行，再结案"
            )

        review = {
            "closed_at": datetime.now(timezone.utc).isoformat(),
            "request": payload,
            "summary": (
                f"工单 {record.ticket_no}；"
                f"处理动作：{record.execution['request']['action']}；"
                f"结果：{request.outcome}；"
                f"改进：{request.improvement}"
            ),
        }

        return _transition(
            session,
            record,
            "executed_mock",
            "closed",
            review=review,
        )