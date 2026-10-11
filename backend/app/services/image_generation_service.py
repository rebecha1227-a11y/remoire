"""Optional image tool for the shared conversation.

Generation finishes before publish. iMessage waits until the turn is still
current; the web saves into shared history as soon as the tool succeeds.
"""
import logging
from app import llm
from app.services import model_settings_service

logger = logging.getLogger(__name__)
TOOL = {"type": "function", "function": {
    "name": "generate_picture",
    "description": "为当前对话现场画一张图片。网页和 iMessage 是同一段对话，两边都会看到这张图；iMessage 线路连着时，网页里画出的图也会发到短信。可以回应用户请求，也可以在合适时主动画图。只传必要的画面描述，不传整段聊天或记忆。每轮最多生成一次；工具返回成功只代表图已生成，不代表对方已经看到。当前只支持文生图，不支持按照片编辑或保证人物相貌一致。",
    "parameters": {"type": "object", "properties": {"prompt": {"type": "string", "description": "完整的画面描述，最多 4000 字"}}, "required": ["prompt"], "additionalProperties": False}}}


async def configured():
    slots = await model_settings_service.list_slots()
    slot = next((s for s in slots if s["slot"] == "image"), None)
    if not slot or not slot.get("preset_id"):
        return None
    preset = await model_settings_service.get_preset(slot["preset_id"])
    if not preset or not model_settings_service.is_image_provider(preset.get("provider")):
        return None
    wire = model_settings_service.resolve_image_wire_protocol(
        preset.get("provider"), preset["base_url"], preset["model_name"],
    )
    return llm.ModelConfig(
        api_base=preset["base_url"],
        api_key=preset["api_key"],
        model_id=preset["model_name"],
        provider=wire,
        slot="image",
    )


async def handle_tool(arguments, turn):
    if turn.get("image_attempted"):
        return "本轮已经尝试过生图，不会重复调用或重复计费。"
    prompt = arguments.get("prompt") if isinstance(arguments, dict) else None
    if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 4000:
        return "未生成：画面描述需要在 1 到 4000 字之间。"
    config = await configured()
    if config is None:
        return "未生成：生图槽位尚未配置。"
    turn["image_attempted"] = True
    try:
        turn["generated_image"] = await llm.generate_image(config, prompt.strip())
    except Exception as exc:
        logger.warning("image_generation_failed %s", type(exc))
        code, detail = llm.public_model_error(exc)
        turn["image_error"] = {"type": "error", "code": code, "content": detail}
        return detail + " 请如实说明，没有图片可发送；本轮不自动重试。"
    return "图片已生成，会留在这段共同对话里。你可以用一两句简短文字补充，也可以只出图、不再加字；不要声称已经送达。"


async def publish_web_image(conversation_id: str, data_url: str) -> dict:
    """Save a web-generated picture into shared history and mirror it when iMessage is live."""
    from app.services.chat_service import save_message
    from app.services.imessage_service import mirror_saved_image

    image_id = await save_message(conversation_id, "assistant", "", image=data_url, channel="remoire")
    try:
        mirrored = await mirror_saved_image(conversation_id, image_id)
    except Exception as exc:
        # A separate delivery failure must never hide an already saved web image.
        logger.warning("image_mirror_failed %s", type(exc))
        mirrored = False
    return {"image_id": image_id, "mirrored": mirrored}
