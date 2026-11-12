from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from claim_models import ClaimRequest, ClaimConfirmRequest
from claim_agent import run_claim_agent
from claim_store import get_claim, confirm_claim
from track.tracking_models import TrackingQueryRequest
from track.tracking_agent import run_tracking_agent

from complaint.complaint_models import (
    ComplaintConfirmRequest,
    ComplaintCloseRequest,
    ComplaintRequest
)
from complaint.complaint_agent import run_complaint_agent
from complaint.complaint_store import (
    save_complaint,
    get_complaint,
    confirm_complaint,
    close_complaint
)

app = FastAPI(
    title="客服Demo",
    version="0.1.0",
)

@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.post("/claims/validate", response_model=ClaimRequest, summary="异常反馈")
def validate_claim(request: ClaimRequest) -> ClaimRequest:
    return request


@app.post("/claims/analyze", summary="Agent 分析物流异常及索赔")
def analyze_claim(request: ClaimRequest):
    return run_claim_agent(request)



@app.get("/claims/{claim_id}", summary="查询索赔记录")
def read_claim(claim_id: str):
    record = get_claim(claim_id)
    if record is None:
        raise HTTPException(status_code=404, detail="没有找到索赔记录")

    return record


@app.post("/claims/{claim_id}/confirm", summary="创建索赔记录")
def confirm_claim_endpoint(claim_id: str, request: ClaimConfirmRequest):
    try:
        return confirm_claim(claim_id, request.operator)
    except LookupError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc



def get_current_user_id() -> str:
    return "USER001"

@app.post("/tracking/query", summary="查询物流信息")
def tranking_query(
    request: TrackingQueryRequest, 
    user_id: str = Depends(get_current_user_id)):
    return run_tracking_agent(request, user_id)



def complaint_call(func, *args):
    try:
        return func(*args)
    except LookupError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc 


@app.post(
    "/complaint/analyze",
    summary="Agent 分析客诉并生成处理建议"
)
def analyze_complaint(
    request: ComplaintRequest,
    user_id: str = Depends(get_current_user_id)
):

    analysis = complaint_call(
        run_complaint_agent,
        request,
        user_id,
    )

    return complaint_call(
        save_complaint,
        request,
        user_id,
        analysis
    )



@app.get("/complaint/{complaint_id}", summary="查询客诉记录")
def read_complaint(
    complaint_id: str,
    user_id: str = Depends(get_current_user_id)
):
    return complaint_call(
        get_complaint,
        complaint_id,
        user_id
    )

@app.post(
    "/complaint/{complaint_id}/confirm",
    summary="确认方案并模拟执行",
)
def confirm_complaint_endpoint(
    complaint_id: str,
    request: ComplaintConfirmRequest,
    user_id: str = Depends(get_current_user_id),
):
    return complaint_call(
        confirm_complaint,
        complaint_id,
        user_id,
        request,
    )


@app.post(
    "/complaint/{complaint_id}/close",
    summary="客诉结案复盘",
)
def close_complaint_endpoint(
    complaint_id: str,
    request: ComplaintCloseRequest,
    user_id: str = Depends(get_current_user_id),
):
    return complaint_call(
        close_complaint,
        complaint_id,
        user_id,
        request,
    )

# --- 中间件配置 (解决跨域问题) ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    # 浏览器不允许通配来源与凭证同时使用；生产环境请配置明确来源以启用凭证。
    allow_credentials= False,
    allow_methods=["*"],
    allow_headers=["*"],
)


import uvicorn
if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)



