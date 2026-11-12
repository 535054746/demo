from claim_tools import (
    query_order,
    query_tracking,
    query_user_orders,
)

CUSTOMERS = {
    "USER001": {
        "level": "VIP",
        "history_tickets": [
            {
                "ticket_no": "HIST001",
                "problem": "物流延迟",
                "resolution": "解释物流后关闭",
            }
        ],
    }
}

ORDER_DETAILS = {
    "DEMO20261112001": {
        "product": "便携风扇",
        "paid_amount": 100.0,
        "currency": "USD",
        "gross_margin_rate": 0.30,
    },
    "DEMO20261112002": {
        "product": "桌面灯具",
        "paid_amount": 80.0,
        "currency": "USD",
        "gross_margin_rate": 0.15,
    },
}


def query_complaint_order(
    user_id: str,
    order_no: str,
    tracking_no: str,
) -> dict:
    """核查用户订单，并查询本次客诉涉及包裹的物流"""
    if order_no not in query_user_orders(user_id)["order_nos"]:
        return {"error": "用户未关联该订单"}

    order = query_order(order_no)

    if "error" in order:
        return order

    numbers = order["tracking_nos"]

    if tracking_no is not None:
        if tracking_no not in numbers:
            return {"error": "未查询到该运单号"}
        numbers = [tracking_no]

    return {
        "order_no": order_no,
        "tracking": [
            query_tracking(order_no, number)
            for number in numbers
        ]
    }


def query_customer_profile(user: str) -> dict:
    """查询客户等级和历史客诉记录"""

    return CUSTOMERS.get(user, {"error": "暂无客户资料，需要人工核实"})


def query_complaint_policy(
    user_id: str,
    order_no: str
) -> dict:
    """查询订单商品信息和处理规则，提供挽留补偿"""
    if order_no not in query_user_orders(user_id)["order_nos"]:
        return {"error": "未找到当前用户的该订单"}

    details = ORDER_DETAILS.get(order_no)

    if details is None:
        return {"error": "暂无该订单商品信息"}

    # 仅为 Demo 规则：
    # 毛利率达到 25% 时，挽留补偿上限为 5。
    cap = (
        5.0
        if details["gross_margin_rate"] >= 0.25
        else 0.0
    )

    # 仅为 Demo 规则：
    # 毛利率达到 25% 时，挽留补偿上限为 5。
    cap = (
        5.0
        if details["gross_margin_rate"] >= 0.25
        else 0.0
    )

    return {
        "demo_only": True,
        "order_details": details,
        "goodwill_cap": cap,
        "currency": details["currency"],
        "requires_human_confirmation": True,
        "rules": [
            "运输中不能直接认定为丢件。",
            "妥投未收到需核实签收证明和收件信息。",
            "破损或错发需收集照片、包装和商品信息。",
            "挽留补偿建议不得超过 goodwill_cap。",
            "goodwill_cap 仅为挽留补偿上限，不是退款额度。",
            "退款、补发和补偿均需客服审核后执行。",
        ],
    }