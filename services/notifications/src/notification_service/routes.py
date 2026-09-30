from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from . import templates
from .config import Settings, get_settings
from .telegram import TelegramClient

router = APIRouter(prefix="/v1/telegram", tags=["telegram"])


def get_client(request: Request) -> TelegramClient:
    return request.app.state.telegram


Client = Annotated[TelegramClient, Depends(get_client)]
Config = Annotated[Settings, Depends(get_settings)]


class TelegramMessage(BaseModel):
    # Numeric id ("-1001234567890") or a public channel username ("@my_channel").
    chat_id: str | None = None
    text: str = Field(min_length=1, max_length=4096)  # Telegram's per-message limit
    parse_mode: Literal["HTML", "MarkdownV2"] | None = None
    disable_notification: bool = False


class TemplateMessage(BaseModel):
    chat_id: str | None = None
    variables: dict[str, str | int | float] = {}
    disable_notification: bool = False


class SentMessage(BaseModel):
    chat_id: str
    message_id: int


async def send(
    client: TelegramClient,
    cfg: Settings,
    chat_id: str | None,
    text: str,
    parse_mode: str | None,
    disable_notification: bool,
) -> SentMessage:
    chat_id = chat_id or cfg.telegram_default_chat_id
    if not chat_id:
        raise HTTPException(422, "chat_id is required (no TELEGRAM_DEFAULT_CHAT_ID set)")
    result = await client.send_message(chat_id, text, parse_mode, disable_notification or None)
    return SentMessage(chat_id=str(result["chat"]["id"]), message_id=result["message_id"])


@router.post("/messages", status_code=201)
async def send_telegram_message(msg: TelegramMessage, client: Client, cfg: Config) -> SentMessage:
    return await send(client, cfg, msg.chat_id, msg.text, msg.parse_mode, msg.disable_notification)


@router.get("/templates")
async def list_templates() -> dict[str, list[str]]:
    """Template name -> the variables it needs."""
    return {name: templates.fields(name) for name in templates.TEMPLATES}


@router.post("/templates/{name}", status_code=201)
async def send_telegram_template(
    name: str, msg: TemplateMessage, client: Client, cfg: Config
) -> SentMessage:
    if name not in templates.TEMPLATES:
        raise HTTPException(404, f"Unknown template '{name}'")
    try:
        text = templates.render(name, msg.variables)
    except templates.TemplateError as exc:
        raise HTTPException(422, str(exc)) from None
    if len(text) > 4096:
        raise HTTPException(422, "rendered message exceeds Telegram's 4096 character limit")
    return await send(client, cfg, msg.chat_id, text, "HTML", msg.disable_notification)
