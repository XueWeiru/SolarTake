# -*- coding: utf-8 -*-
"""LLM 服務層：prompt、模型呼叫、示範模式都集中在這裡。
這個檔案不 import FastAPI，所以可以單獨測試（注入假的 client 即可）。"""

from collections.abc import Iterator

import anthropic

from app.core.config import settings
from app.schemas.llm import ChatMessage, ReportContext

SYSTEM_PROMPT = (
    "你是台灣住宅太陽能裝設評估顧問。用親切易懂的繁體中文向屋主說明，"
    "不使用條列式法規名稱，並清楚標示數字是估算值而非保證值。"
    "只能引用使用者提供的數字，不要自行編造或重新計算。"
)


def _payback_text(ctx: ReportContext) -> str:
    return "無法回本（節省金額為 0）" if ctx.payback_years is None else f"{ctx.payback_years:.1f} 年"


def build_facts(ctx: ReportContext) -> str:
    return (
        f"地址：{ctx.address}\n"
        f"建議裝設容量：{ctx.peak_power_kwp:.1f} kWp\n"
        f"屋頂朝向：{ctx.aspect_name}，傾角：{ctx.tilt_deg:.0f} 度\n"
        f"估算年發電量：{ctx.annual_kwh:.0f} 度\n"
        f"系統總損失估算：{ctx.annual_loss_pct:.1f}%\n"
        f"系統造價估算：{ctx.system_cost:.0f} 元（已扣除補助）\n"
        f"每年估算節省電費：{ctx.annual_saving:.0f} 元\n"
        f"簡易回本年限：{_payback_text(ctx)}\n"
    )


def build_report_prompt(ctx: ReportContext) -> str:
    return (
        "請根據以下資料寫約 200-300 字的評估說明，內容包含：划不划算、"
        "大致多久回本、需要注意的風險或限制。\n\n" + build_facts(ctx)
    )


def build_demo_report(ctx: ReportContext) -> str:
    return (
        "【示範模式報告，非 AI 生成】\n\n"
        f"此地點裝設 {ctx.peak_power_kwp:.1f} kWp 後，估算年發電量約 {ctx.annual_kwh:.0f} 度，"
        f"系統總損失約 {ctx.annual_loss_pct:.1f}%。簡易回本年限約 {_payback_text(ctx)}。\n\n"
        "提醒：以上為估算值，實際會受遮蔭、面板衰減、饋線容量等因素影響，正式規劃仍建議實地會勘。\n"
        "（後端未設定 ANTHROPIC_API_KEY，所以顯示樣板文字。）"
    )


class LLMService:
    def __init__(self, client: anthropic.Anthropic | None = None):
        key = settings.ANTHROPIC_API_KEY
        print("KEY CHECK:", None if not key else (len(key), key[:12], key[-4:], repr(key[-1])))
        # 允許外部注入 client（測試時傳假物件）；否則用 settings 的金鑰建立
        if client is None and settings.ANTHROPIC_API_KEY:
            client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        self._client = client

    @property
    def enabled(self) -> bool:
        return self._client is not None

    def stream_report(self, ctx: ReportContext) -> Iterator[str]:
        if not self.enabled:
            yield build_demo_report(ctx)
            return
        messages = [{"role": "user", "content": build_report_prompt(ctx)}]
        yield from self._stream(SYSTEM_PROMPT, messages)

    def stream_chat(self, ctx: ReportContext, messages: list[ChatMessage]) -> Iterator[str]:
        if not self.enabled:
            yield "（示範模式：後端未設定 ANTHROPIC_API_KEY，無法回答追問。）"
            return
        system = SYSTEM_PROMPT + "\n\n以下是這位屋主的評估資料：\n" + build_facts(ctx)
        yield from self._stream(system, [m.model_dump() for m in messages])

    def _stream(self, system: str, messages: list[dict]) -> Iterator[str]:
        """出錯時把錯誤訊息當文字回傳，前端不需特別處理。"""
        try:
            with self._client.messages.stream(
                model=settings.LLM_MODEL,
                max_tokens=settings.LLM_MAX_TOKENS,
                system=system,
                messages=messages,
            ) as stream:
                for text in stream.text_stream:
                    yield text
        except anthropic.APIError as e:
            yield f"\n\n⚠️ LLM 呼叫失敗：{e}"
