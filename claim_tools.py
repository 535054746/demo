from datetime import datetime


# 固定演示时间，保证每次验证结果一致。
DEMO_NOW = datetime.fromisoformat("2026-11-12T12:00:00+08:00")
STALL_DAYS = 7

# 模拟 ERP：订单对应的全部运单号。
ORDERS = {
    "DEMO20261112001": ["DEMO_TRACK_001"],
    "DEMO20261112002": ["DEMO_TRACK_002", "DEMO_TRACK_003"],
}

# 模拟物流查询结果。
TRACKING = {
    "DEMO_TRACK_001": {
        "status": "in_transit",
        "last_update": "2026-11-01T12:00:00+08:00",
    },
    "DEMO_TRACK_002": {
        "status": "delivered",
        "last_update": "2026-11-10T12:00:00+08:00",
    },
    "DEMO_TRACK_003": {
        "status": "in_transit",
        "last_update": "2026-11-10T12:00:00+08:00",
    },
}


def query_order(order_no: str) -> dict:
    """查询模拟 ERP，获取指定订单关联的全部运单号。"""
    numbers = ORDERS.get(order_no)

    if numbers is None:
        return {"error": "未查询到该订单"}

    return {
        "order_no": order_no,
        "tracking_nos": numbers,
    }


def query_tracking(order_no: str, tracking_no: str) -> dict:
    """查询指定订单下包裹的模拟物流状态和最后更新时间。"""
    if tracking_no not in ORDERS.get(order_no, []):
        return {"error": "订单不存在，或运单不属于该订单"}

    data = TRACKING.get(tracking_no)

    if data is None:
        return {"error": "暂无该包裹的物流数据"}

    return {
        "order_no": order_no,
        "tracking_no": tracking_no,
        **data,
    }


def check_claim_rules(
    order_no: str,
    tracking_no: str,
    problem_type: str,
) -> dict:
    """根据模拟物流和演示规则核验索赔条件，返回结论及依据。"""
    tracking = query_tracking(order_no, tracking_no)

    if "error" in tracking:
        return {
            "decision": "manual_review",
            "reason": tracking["error"],
        }

    # 规则一：妥投未收到，交给人工核实。
    if problem_type == "delivered_not_received":
        return {
            "decision": "manual_review",
            "rule": "DEMO_DELIVERED_NOT_RECEIVED",
            "tracking_status": tracking["status"],
            "reason": "需要核实实际物流状态、签收证明和收件信息。",
        }

    # 规则二：运输中的包裹，判断停滞时间。
    if (
        problem_type == "tracking_stalled"
        and tracking["status"] == "in_transit"
    ):
        updated_at = datetime.fromisoformat(tracking["last_update"])
        days = (DEMO_NOW - updated_at).days

        if days < 0:
            return {
                "decision": "manual_review",
                "reason": "物流时间需要核实",
            }

        return {
            "decision": (
                "can_apply" if days >= STALL_DAYS else "not_eligible"
            ),
            "rule": "DEMO_STALLED",
            "days_without_update": days,
            "threshold_days": STALL_DAYS,
            "reason": (
                "达到演示停滞阈值，可准备申请材料。"
                if days >= STALL_DAYS
                else "尚未达到演示停滞阈值。"
            ),
        }

    return {
        "decision": "manual_review",
        "reason": "当前问题或物流状态未覆盖自动判断规则，需要人工核实。",
    }

"""模拟用户订单,创建多个用户订单"""
USER_ORDERS = {
    "USER001": [
        "DEMO20261112001",
        "DEMO20261112002",
    ],
    "USER002": [],
}


def query_user_orders(user_id: str) -> dict:
    """查询指定用户关联的全部订单号。"""
    return {
        "order_nos": USER_ORDERS.get(user_id, []),
    }