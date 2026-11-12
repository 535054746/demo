from pathlib import Path
from uuid import uuid4

from sqlalchemy import (
    JSON,
    String,
    UniqueConstraint,
    create_engine,
    select,
    update,
)

from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.engine import URL
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    sessionmaker,
)


from claim_models import ClaimRequest
from claim_tools import (
    query_order,
    check_claim_rules
)
DB_PATH = Path(__file__).with_name("claim_demo.db")


class Base(DeclarativeBase):
    pass


class ClaimRecord(Base):
    __tablename__ = "claims"

    __table_args__ = (
        UniqueConstraint(
            "order_no",
            "tracking_no",
            "problem_type",
            name="uq_claim_business",
        ),
    )
    claim_id: Mapped[str] = mapped_column(
        String(40),
        primary_key=True,
    )
    order_no: Mapped[str] = mapped_column(String(64))
    tracking_no: Mapped[str] = mapped_column(String(64))
    problem_type: Mapped[str] = mapped_column(String(40))

    request_json: Mapped[dict] = mapped_column(JSON)
    rule_result: Mapped[dict] = mapped_column(JSON)

    status: Mapped[str] = mapped_column(String(32))

    after_sale_no: Mapped[str | None] = mapped_column(String(40))
    claim_no: Mapped[str | None] = mapped_column(String(40))
    confirmed_by: Mapped[str | None] = mapped_column(String(64))



engine = create_engine(
    URL.create(
        "sqlite",
        database=str(DB_PATH)
    ),
    connect_args={"check_same_thread": False, "timeout": 60},
)


SessionLocal = sessionmaker(bind=engine)

Base.metadata.create_all(engine)


def to_record(record: ClaimRecord | None ) -> dict | None:
    if record is None:
        return None
    return {
        "claim_id": record.claim_id,
        "order_no": record.order_no,
        "tracking_no": record.tracking_no,
        "problem_type": record.problem_type,
        "request": record.request_json,
        "rule_result": record.rule_result,
        "status": record.status,
        "after_sale_no": record.after_sale_no,
        "claim_no": record.claim_no,
        "confirmed_by": record.confirmed_by,
    }


def prepare_claim(request: ClaimRequest) -> dict:

    order = query_order(request.order_no)
    if "error" in order:
        return order

    tracking_no = request.tracking_no

    if tracking_no is None:
        numbers = order["tracking_nos"]

        if len(numbers) != 1:
            return {
                "error": "请明确需要索赔的运单",
                "tracking_nos": numbers
            }
        tracking_no = numbers[0]

    rule = check_claim_rules(
        request.order_no,
        tracking_no,
        request.problem_type,
    )
    if rule["decision"] != "can_apply":
        return {
            "error": "当前不能创建自动索赔草稿",
            "rule_result": rule,
        }

    resolved = request.model_copy(
        update={
            "tracking_no": tracking_no,
        }
    )

    with SessionLocal.begin() as session:

        statement = (
            insert(ClaimRecord)
            .values(
                claim_id=f"CASE-{uuid4().hex}",
                order_no=request.order_no,
                tracking_no=tracking_no,
                problem_type=request.problem_type,
                request_json=resolved.model_dump(),
                rule_result=rule,
                status="pending_confirmation"
            )
            .on_conflict_do_nothing(
                index_elements=["order_no", "tracking_no", "problem_type"],
            )
        )
        session.execute(statement)

        record = session.scalar(
            select(ClaimRecord).where(
                ClaimRecord.order_no == request.order_no,
                ClaimRecord.tracking_no == tracking_no,
                ClaimRecord.problem_type == request.problem_type,
            )
        )

        return to_record(record)


def get_claim(claim_id: str) -> dict | None:
    with SessionLocal() as session:
        record = session.get(ClaimRecord, claim_id)
        return to_record(record)

def confirm_claim(claim_id: str, operator: str) -> dict:
    """客户确定，等级索赔"""
    with SessionLocal.begin() as session:
        record = session.get(ClaimRecord, claim_id)

        if record is None:
            raise LookupError("没有找到索赔记录")

        if record.status == "submitted_mock":
            return to_record(record)

        rule = check_claim_rules(
            record.order_no,
            record.tracking_no,
            record.problem_type,
        )

        if rule["decision"] != "can_apply":
            raise ValueError(
                "确认时规则复核未通过：" + rule["reason"]
            )

        session.execute(
            update(ClaimRecord)
            .where(ClaimRecord.claim_id == claim_id, ClaimRecord.status == "pending_confirmation")
            .values(
                status="submitted_mock",
                after_sale_no=f"MOCK-AS-{uuid4().hex[:12]}",
                claim_no=f"MOCK-CL-{uuid4().hex[:12]}",
                confirmed_by=operator,
                rule_result=rule
            )
        )
        session.refresh(record)
        return to_record(record)