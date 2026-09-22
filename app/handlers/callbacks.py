"""Inline-button router.

All conversation state lives in the chats table, never in memory — a redeploy
mid-setup must not strand anyone.
"""
import logging

from telegram import Update
from telegram.ext import ContextTypes

from app import db, formatting, i18n, keyboards
from app.berlin_districts import DISTRICTS
from app.handlers import _ui
from app.providers import PROVIDER_KEYS

logger = logging.getLogger("wohnwatch.callbacks")

# Which screen a set/toggle action belongs to, so we can re-render in place.
_SCREEN_OF = {
    "rmin": "rmin", "rmax": "rmax", "rent": "rent", "size": "size", "wbs": "wbs",
}

_FIELD_OF = {"rmin": "rooms_min", "rmax": "rooms_max", "rent": "max_rent", "size": "min_size"}


async def route(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    chat_id = update.effective_chat.id
    chat = db.ensure_chat(chat_id)
    lang = chat["language"]
    parts = (query.data or "").split(":")
    action = parts[0]

    # A second, older keyboard in the same chat would edit the wrong message.
    if action not in ("del", "nop") and chat["menu_msg_id"] not in (None, query.message.message_id):
        await query.answer(i18n.t("STALE_MENU", lang), show_alert=False)
        await _render_fresh(context, chat_id, lang)
        return

    await query.answer()
    handler = _HANDLERS.get(action)
    if handler is None:
        logger.warning("unknown callback %r", query.data)
        return
    await handler(query, context, chat_id, parts[1:], lang)


# -- helpers ----------------------------------------------------------------

def _is_wizard(chat_id: int) -> bool:
    chat = db.get_chat(chat_id)
    return bool(chat and chat["state"] == "setup")


async def _render_fresh(context, chat_id: int, lang: str) -> None:
    """Replace a stale menu with a new message at the chat's current position."""
    chat = db.get_chat(chat_id)
    f = db.get_filter(chat_id)
    step = chat["setup_step"] if chat else ""
    if step == "confirm":
        text, markup = keyboards.render_confirm(f, lang)
    elif step in keyboards.WIZARD_SCREENS:
        text, markup = keyboards.render_screen(step, f, lang, wizard=True)
    else:
        text, markup = keyboards.render_root(f, lang)
    await _ui.send_menu(context.bot, chat_id, text, markup)


async def _show_screen(query, chat_id: int, screen: str, lang: str) -> None:
    wizard = _is_wizard(chat_id)
    if wizard:
        db.set_chat(chat_id, setup_step=screen)
    text, markup = keyboards.render_screen(screen, db.get_filter(chat_id), lang, wizard=wizard)
    await _ui.edit_menu(query, text, markup)


# -- actions ----------------------------------------------------------------

async def _on_menu(query, context, chat_id, args, lang) -> None:
    target = args[0] if args else "root"
    db.set_chat(chat_id, awaiting="")
    if target == "root":
        # "Nochmal bearbeiten" / "Zurück" leaves the wizard for the flat menu.
        db.set_chat(chat_id, setup_step="")
        text, markup = keyboards.render_root(db.get_filter(chat_id), lang)
        await _ui.edit_menu(query, text, markup)
        return
    await _show_screen(query, chat_id, target, lang)


async def _on_wizard(query, context, chat_id, args, lang) -> None:
    move = args[0] if args else "next"
    chat = db.get_chat(chat_id)

    if move == "start":
        db.set_chat(chat_id, state="setup", setup_step=keyboards.WIZARD_SCREENS[0], awaiting="")
        text, markup = keyboards.render_screen(
            keyboards.WIZARD_SCREENS[0], db.get_filter(chat_id), lang, wizard=True
        )
        await _ui.edit_menu(query, text, markup)
        return

    step = chat["setup_step"]
    if step not in keyboards.WIZARD_SCREENS:
        await _on_menu(query, context, chat_id, ["root"], lang)
        return

    idx = keyboards.WIZARD_SCREENS.index(step)
    idx = idx - 1 if move == "back" else idx + 1

    if idx < 0:
        await _on_menu(query, context, chat_id, ["root"], lang)
        return
    if idx >= len(keyboards.WIZARD_SCREENS):
        db.set_chat(chat_id, setup_step="confirm")
        text, markup = keyboards.render_confirm(db.get_filter(chat_id), lang)
        await _ui.edit_menu(query, text, markup)
        return

    await _show_screen(query, chat_id, keyboards.WIZARD_SCREENS[idx], lang)


async def _on_set(query, context, chat_id, args, lang) -> None:
    key, raw = args[0], args[1]
    if key == "wbs":
        db.update_filter(chat_id, {"wbs_required": "" if raw == keyboards.ANY else raw})
        await _show_screen(query, chat_id, "wbs", lang)
        return

    field = _FIELD_OF[key]
    value = None if raw == keyboards.ANY else float(raw)
    db.update_filter(chat_id, {field: value})
    _fix_room_bounds(chat_id, field)
    await _show_screen(query, chat_id, _SCREEN_OF[key], lang)


def _fix_room_bounds(chat_id: int, changed: str) -> None:
    """Keep rooms_min <= rooms_max; otherwise the filter can never match."""
    f = db.get_filter(chat_id)
    lo, hi = f.get("rooms_min"), f.get("rooms_max")
    if lo is None or hi is None or lo <= hi:
        return
    other = "rooms_max" if changed == "rooms_min" else "rooms_min"
    db.update_filter(chat_id, {other: f[changed]})


async def _on_ask(query, context, chat_id, args, lang) -> None:
    key = args[0]
    field = keyboards.ASK_FIELDS[key]
    db.set_chat(chat_id, awaiting=field)
    await _ui.edit_menu(query, i18n.t(f"ASK_NUMBER_{field.upper()}", lang) + i18n.t("ASK_HINT", lang))


async def _on_toggle(query, context, chat_id, args, lang) -> None:
    kind, value = args[0], args[1]
    f = db.get_filter(chat_id)
    if kind == "d":
        idx = int(value)
        if not 0 <= idx < len(DISTRICTS):
            return
        db.update_filter(chat_id, {
            "districts": formatting.toggle_csv(f.get("districts"), DISTRICTS, DISTRICTS[idx])
        })
        await _show_screen(query, chat_id, "dist", lang)
    else:
        if value not in PROVIDER_KEYS:
            return
        db.update_filter(chat_id, {
            "providers": formatting.toggle_csv(f.get("providers"), PROVIDER_KEYS, value)
        })
        await _show_screen(query, chat_id, "prov", lang)


async def _on_all(query, context, chat_id, args, lang) -> None:
    kind = args[0]
    if kind == "d":
        db.update_filter(chat_id, {"districts": ""})
        await _show_screen(query, chat_id, "dist", lang)
    else:
        db.update_filter(chat_id, {"providers": ""})
        await _show_screen(query, chat_id, "prov", lang)


async def _on_filter_action(query, context, chat_id, args, lang) -> None:
    what = args[0]
    if what == "clear":
        db.clear_filter(chat_id)
        text, markup = keyboards.render_root(db.get_filter(chat_id), lang)
        await _ui.edit_menu(query, f"{i18n.t('FILTER_CLEARED', lang)}\n\n{text}", markup)
        return

    if what == "help":
        await _ui.edit_menu(query, i18n.t("HELP", lang))
        return

    if what in ("activate", "done"):
        chat = db.get_chat(chat_id)
        if chat["state"] in ("new", "setup"):
            _ui.activate(chat_id)
            await _ui.edit_menu(query, i18n.t("SETUP_DONE", lang,
                summary=formatting.filter_summary(db.get_filter(chat_id), lang)
            ))
        else:
            db.set_chat(chat_id, setup_step="", awaiting="")
            await _ui.edit_menu(query, i18n.t("MENU_TITLE", lang,
                summary=formatting.filter_summary(db.get_filter(chat_id), lang)
            ))


async def _on_delete(query, context, chat_id, args, lang) -> None:
    if args and args[0] == "yes":
        db.delete_chat(chat_id)
        await _ui.edit_menu(query, i18n.t("DELETED", lang))
    else:
        await _ui.edit_menu(query, i18n.t("DELETE_ABORTED", lang))


async def _on_language(query, context, chat_id, args, lang) -> None:
    new_lang = args[0] if args else ""
    if new_lang not in i18n.SUPPORTED_LANGUAGES:
        return
    db.set_chat(chat_id, language=new_lang)
    await _ui.edit_menu(query, i18n.t("LANGUAGE_SET", new_lang))
    # The currently open menu (if any) should reflect the new language too.
    await _render_fresh(context, chat_id, new_lang)


async def _on_nop(query, context, chat_id, args, lang) -> None:
    return


_HANDLERS = {
    "m": _on_menu,
    "w": _on_wizard,
    "set": _on_set,
    "ask": _on_ask,
    "tog": _on_toggle,
    "all": _on_all,
    "f": _on_filter_action,
    "del": _on_delete,
    "lang": _on_language,
    "nop": _on_nop,
}
