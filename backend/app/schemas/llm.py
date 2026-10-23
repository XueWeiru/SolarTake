# -*- coding: utf-8 -*-
"""LLM 相關的請求格式（schemas 層：只定義資料形狀，不放邏輯）。"""

from typing import Literal

from pydantic import BaseModel


class ReportContext(BaseModel):
    """產生報告所需的評估結果。
    若你的 schemas/assessment.py 已有相同欄位，可改成繼承或直接由
    Assessment 轉換，避免重複定義。"""

    address: str
    aspect_name: str
    tilt_deg: float
    peak_power_kwp: float
    annual_kwh: float
    annual_loss_pct: float
    system_cost: float
    annual_saving: float
    payback_years: float | None = None  # 無法回本時為 None


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    ctx: ReportContext
    messages: list[ChatMessage]
