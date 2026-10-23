# -*- coding: utf-8 -*-
"""LLM 路由：只負責收請求、呼叫 service、回傳串流。不放 prompt 或模型邏輯。"""

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

# 依你的 deps.py 實際名稱調整這兩個 import
from app.api.deps import get_current_user, get_llm_service
from app.schemas.llm import ChatRequest, ReportContext
from app.services.llm_service import LLMService

router = APIRouter(prefix="/llm", tags=["llm"])

TEXT_STREAM = "text/plain; charset=utf-8"


@router.post("/report")
def create_report(
    ctx: ReportContext,
    llm: LLMService = Depends(get_llm_service),
    user=Depends(get_current_user),  # 擋掉未登入者，避免被盜刷金鑰額度
):
    return StreamingResponse(llm.stream_report(ctx), media_type=TEXT_STREAM)


@router.post("/chat")
def chat(
    req: ChatRequest,
    llm: LLMService = Depends(get_llm_service),
    user=Depends(get_current_user),
):
    return StreamingResponse(llm.stream_chat(req.ctx, req.messages), media_type=TEXT_STREAM)
