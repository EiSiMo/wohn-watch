"""English strings — see app/i18n/de.py for the key inventory and structure
this mirrors. tests/test_i18n.py keeps the two files in sync (same keys,
same .format() placeholders).
"""

STRINGS: dict[str, str] = {
    # -- top-level flows -----------------------------------------------------
    "INTRO": (
        "*Wohn-Watch* 🏠\n\n"
        "I watch the apartment finder at *inberlinwohnen.de* around the clock — "
        "the joint portal of Berlin's six state-owned housing associations "
        "(Gewobag, degewo, GESOBAU, HOWOGE, Stadt und Land, WBM).\n\n"
        "Tell me once what you're looking for. As soon as a new listing matches, "
        "I'll send it to you right here — with address, rent, size, and a link to the listing.\n\n"
        "No account, no sign-up, free. /stop deletes all your data at any time.\n\n"
        "Let's set up your filter 👇"
    ),
    "INTRO_RETURNING": (
        "Welcome back 🏠\n\n"
        "Your filter: _{summary}_\n"
        "Status: *{state}*\n\n"
        "/filter changes your search, /status shows details."
    ),
    "HELP": (
        "*Wohn-Watch — Help*\n\n"
        "I'll notify you about new apartments on inberlinwohnen.de that match your filter.\n\n"
        "*Commands*\n"
        "/start – Introduction and setup\n"
        "/filter – Change your search\n"
        "/status – current filter and stats\n"
        "/pause – pause notifications\n"
        "/resume – resume notifications\n"
        "/problem – report a problem or request\n"
        "/stop – delete all data\n"
        "/language – switch language (Deutsch/English)\n"
        "/help – this overview\n\n"
        "*Your data*\n"
        "I store your chat ID, your filter, and a log of your messages to me — "
        "so I can see whether the bot works and is being used. "
        "No names, no phone number, no sharing with third parties. "
        "/stop deletes all of it immediately and completely.\n\n"
        "*Important*\n"
        "I don't apply for you automatically. You get the link, you have to apply yourself — "
        "every minute counts for the sought-after apartments.\n\n"
        "Source code: https://github.com/EiSiMo/wohn-watch"
    ),
    "SETUP_DONE": (
        "✅ *Alerts are active.*\n\n"
        "Your filter: _{summary}_\n\n"
        "From now on I'll notify you about every new matching apartment. Apartments that "
        "were already online before this setup are deliberately skipped — otherwise you'd "
        "see a hundred outdated listings right away.\n\n"
        "⚡️ *Be quick.* Listings are often gone again after about 30 minutes. "
        "When a message arrives, it pays to react right away and apply immediately — "
        "not just in the evening.\n\n"
        "/pause takes a short break, /filter changes your search."
    ),
    "MENU_TITLE": "*Your filter*\n_{summary}_",
    "STATUS": (
        "*Status*\n\n"
        "Notifications: *{state}*\n"
        "Filter: _{summary}_\n"
        "Reported so far: *{sent}* apartments\n"
        "Listings tracked: *{flats}*\n"
        "Last check: {last_scrape}"
    ),
    "STATE_ACTIVE": "active",
    "STATE_PAUSED": "paused",
    "STATE_NEW": "not set up yet",
    "NOT_SET_UP": "You don't have a filter yet. Start with /start.",
    "PAUSED": "⏸ Notifications paused. /resume to continue.",
    "ALREADY_PAUSED": "Already paused. /resume to continue.",
    "RESUMED": (
        "▶️ Notifications are running again.\n\n"
        "I'll start from now — anything that went online during the pause won't be caught up on."
    ),
    "ALREADY_ACTIVE": "Already running. /pause suspends it.",
    "DELETE_CONFIRM": (
        "Really delete everything?\n\n"
        "Your filter and all stored data for this chat will be gone for good. "
        "You can start over with /start at any time."
    ),
    "DELETED": "🗑 Everything deleted. Thanks for trying it out — /start brings you back any time.",
    "DELETE_ABORTED": "Cancelled, everything stays as it is.",

    "ASK_NUMBER_ROOMS_MIN": "How many rooms *at minimum*? Send me a number, e.g. `2` or `2.5`.",
    "ASK_NUMBER_ROOMS_MAX": "How many rooms *at most*? Send me a number, e.g. `3.5`.",
    "ASK_NUMBER_MAX_RENT": "What's the highest *total rent* you'll pay? A number in euros, e.g. `1250`.",
    "ASK_NUMBER_MIN_SIZE": "What's the minimum *living space*? A number in m², e.g. `60`.",
    "ASK_HINT": "\n\n_Cancel with /filter._",

    "BAD_NUMBER": "I couldn't read that as a number. Try again, e.g. `1250`.",
    "OUT_OF_RANGE": "That value looks unrealistic ({lo}–{hi}). Please send me a different number.",

    "UNEXPECTED_TEXT": (
        "I don't understand that 🤔 I only understand commands:\n\n"
        "/start – Introduction and setup\n"
        "/filter – Change your search\n"
        "/status – current filter and stats\n"
        "/pause – pause notifications\n"
        "/resume – resume notifications\n"
        "/problem – something wrong?\n"
        "/stop – delete all data\n"
        "/language – switch language\n"
        "/help – detailed overview"
    ),

    "PROBLEM": (
        "*Something wrong?*\n\n"
        "Just send me an email — bugs, odd matches, missing "
        "apartments, or requests, all welcome:\n\n"
        "{support_email}\n\n"
        "Helpful for me: what you expected and what happened instead. "
        "/status shows your current filter — feel free to include it."
    ),

    "STALE_MENU": "This menu is outdated — I've opened a fresh one for you.",

    "OVERFLOW": (
        "… and *{n}* more matching apartments this round.\n"
        "Your filter is pretty broad — /filter lets you narrow it down."
    ),

    "WIZARD_STEP": "*Step {n} of {total}*\n\n{question}",

    "Q_ROOMS_MIN": "How many rooms do you need *at minimum*?",
    "Q_ROOMS_MAX": "And how many rooms *at most*?",
    "Q_RENT": "What's the highest *total rent* you'll pay?",
    "Q_SIZE": "What's the minimum *living space* you need?",
    "Q_WBS": (
        "Do you need apartments *with* or *without* a WBS?\n\n"
        "_A Wohnberechtigungsschein (WBS) is required for many affordable apartments. "
        "If you don't have one, choose “without WBS only”._"
    ),
    "Q_DISTRICTS": (
        "Which *districts* are you searching in?\n\n"
        "_Select nothing = all districts._"
    ),
    "Q_PROVIDERS": (
        "Which *providers*?\n\n"
        "_Select nothing = all providers._"
    ),

    "SUMMARY_CONFIRM": (
        "Here's what I've got:\n\n_{summary}_\n\n"
        "Does that look right?"
    ),

    "FILTER_CLEARED": "Filter reset — you'll get all new apartments again now.",

    # -- keyboard button labels (app/keyboards.py) ---------------------------
    "NAV_BACK": "‹ Back",
    "NAV_NEXT": "Next ›",
    "OPT_ANY": "any",
    "CUSTOM_VALUE": "Custom value",
    "WBS_OPT_NO": "without WBS only",
    "WBS_OPT_YES": "with WBS only",
    "SELECT_ALL": "Select all",
    "ACTIVATE_ALARMS": "Activate alerts",
    "EDIT_AGAIN": "Edit again",
    "SETUP_FILTER": "Set up filter",
    "JUST_LOOKING": "Just looking for now",
    "CONFIRM_DELETE_YES": "Yes, delete everything",
    "CANCEL": "Cancel",
    "RESET_FILTER": "Reset filter",
    "DONE": "Done",
    "ROOT_ROOMS_MIN": "Rooms from: {value}",
    "ROOT_ROOMS_MAX": "Rooms to: {value}",
    "ROOT_RENT": "Rent: {value}",
    "ROOT_SIZE": "Size: {value}",
    "ROOT_WBS": "WBS: {value}",
    "ROOT_DISTRICTS": "Districts: {value}",
    "ROOT_PROVIDERS": "Providers: {value}",

    # -- match message + filter labels (app/formatting.py) -------------------
    "WBS_REQUIRED": "required",
    "WBS_NOT_REQUIRED": "not required",
    "MATCH_RENT_LABEL": "Rent: ",
    "MATCH_SIZE_LABEL": "Size: ",
    "MATCH_ROOMS_LABEL": "Rooms: ",
    "MATCH_WBS_LABEL": "WBS: ",
    "MATCH_PROVIDER_LABEL": "Provider: ",
    "MATCH_LINK_LABEL": "View original listing",
    "LABEL_ROOMS_FROM": "from {value}",
    "LABEL_ROOMS_TO": "up to {value}",
    "LABEL_ROOMS_RANGE": "{lo}–{hi}",
    "LABEL_RENT_MAX": "max. {value} €",
    "LABEL_SIZE_MIN": "from {value} m²",
    "LABEL_ALL": "all",
    "LABEL_SELECTED_N": "{n} selected",
    "LABEL_NO_RESTRICTION": "no restrictions",
    "LABEL_WITH_WBS": "with WBS",
    "LABEL_WITHOUT_WBS": "without WBS",
    "UNIT_ROOMS_SUFFIX": "rooms",
    "UNIT_DISTRICT_SINGULAR": "district",
    "UNIT_DISTRICT_PLURAL": "districts",
    "UNIT_PROVIDER_SINGULAR": "provider",
    "UNIT_PROVIDER_PLURAL": "providers",
    "MONEY_FORMAT": "{amount} €",

    # -- command descriptions (BotFather menu) --------------------------------
    "CMD_DESC_START": "Introduction and setup",
    "CMD_DESC_FILTER": "Change your search",
    "CMD_DESC_STATUS": "Filter and stats",
    "CMD_DESC_PAUSE": "Pause notifications",
    "CMD_DESC_RESUME": "Resume notifications",
    "CMD_DESC_PROBLEM": "Report a problem",
    "CMD_DESC_STOP": "Delete all data",
    "CMD_DESC_HELP": "Overview of all commands",
    "CMD_DESC_LANGUAGE": "Switch language",

    # -- /language UI ---------------------------------------------------------
    "LANGUAGE_PROMPT": "Which language?",
    "LANGUAGE_SET": "✅ Language updated.",
}
