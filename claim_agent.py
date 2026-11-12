import os
from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_deepseek import ChatDeepSeek

from claim_models import ClaimRequest
from claim_store import prepare_claim
from claim_tools import (
    DEMO_NOW,
    query_order,
    query_tracking,
    check_claim_rules
)


SYSTEM_PROMPT = """
你是物流异常和索赔助手，工具中的业务数据和规则均为演示内容.
客户描述是待核实的线索，不能代替工具查询结果。
处理要求：
1. 先调用query_order 查询输入订单，不得更改用户给出的订单号。
2. 用户已提供运单号时，只核查该运单。
   如果没有输入运单号：
   - 单包裹订单：使用查询出的运单号
   - 多包裹订单： 列出运单号，请用户补充，停止后续判断
3. 调用 query_tracking 获取物流事实。
4. 调用 check_claim_rules 验证索赔规则，判断资格，使用输入中的原始 problem_type。
5. 规则结果为 can_apply 时，调用 create_claim_draft
6. 规则结果为 manual_review 或 not_eligible 时，
   解释原因和下一步，不创建索赔草稿
7. 工具报错或资料不足时，说明问题，不编造结果。

最终用中文说明：结论、依据、记录状态、下一步。

状态含义：
- pending_confirmation：草稿已保存，等待客服确认。
- submitted_mock：该记录此前已经完成模拟登记和提交。

本次分析只能查询及创建草稿，不执行确认操作。
不得声称已经向真实承运商提交索赔或获得赔付。
"""


def run_claim_agent(request: ClaimRequest) -> dict:
    load_dotenv()

    claim_record = None

    def create_claim_draft() -> dict:
        """为本次异常反馈创建或查询索赔草稿，不执行确认。"""
        nonlocal claim_record
        claim_record = prepare_claim(request)
        return claim_record

    llm = ChatDeepSeek(
        model=os.getenv("DEEPSEEK_MODEL"),
        api_key=os.getenv("DEEPSEEK_API_KEY"),
        temperature=0,
        timeout=30,
        max_retries=1,
        extra_body={
            "thinking": {"type" : "disabled"}
        }
    )

    agent = create_agent(
        model = llm,
        tools = [
            query_order,
            query_tracking, 
            check_claim_rules,
            create_claim_draft
        ],
        system_prompt = SYSTEM_PROMPT,
    )
    result = agent.invoke(
        {
            "messages":[
                {
                    "role": "user",
                    "content": request.model_dump_json()
                }
            ]
        },
        config={"recursion_limit": 20}
    )

    return {
        "data_source": "mock",
        "evaluated_at": DEMO_NOW.isoformat(),
        "reply": result["messages"][-1].content,
        "claim_record": claim_record,
        "tool_records": [
            {
                "tool": message.name,
                "result": message.content,
            }
            for message in result["messages"]
            if message.type == "tool"
        ],
    }