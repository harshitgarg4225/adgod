"""Ad-style templates — the handful of proven ad-copy frameworks an owner can pick from,
in plain words (not marketing jargon). The owner chooses "what kind of ad" they want; the
Maker agent turns that choice into on-brand, Meta-compliant copy.

`ad_style = None` on an account means "let Saathi choose the best style" — the default, and
the least-effort option for a non-technical owner. These frameworks are the standard public
ad-copy patterns (offer, social proof, problem→solution, urgency, seasonal, curiosity)."""
from __future__ import annotations

# key → localized owner-facing label/description + the guidance Maker follows.
# Labels are deliberately concrete ("Discount or special offer") not abstract
# ("value proposition") so a salon owner instantly knows which to tap.
AD_STYLES: dict[str, dict] = {
    "offer": {
        "emoji": "🏷️",
        "label": {"en": "Discount or special offer", "hi": "छूट या खास ऑफर",
                  "pa": "ਛੂਟ ਜਾਂ ਖਾਸ ਆਫ਼ਰ"},
        "desc": {"en": "Lead with a deal — a price, a discount, a freebie.",
                 "hi": "ऑफर सबसे आगे — कीमत, छूट या फ्री चीज़।",
                 "pa": "ਆਫ਼ਰ ਸਭ ਤੋਂ ਅੱਗੇ — ਕੀਮਤ, ਛੂਟ ਜਾਂ ਮੁਫ਼ਤ ਚੀਜ਼।"},
        "guidance": (
            "OFFER style: lead with a concrete deal — a specific price, a percentage "
            "discount, or a free add-on. Make the saving unmistakable and the CTA direct. "
            "Never invent a discount the brief doesn't support."
        ),
    },
    "festival": {
        "emoji": "🎉",
        "label": {"en": "Festival or seasonal", "hi": "त्योहार या मौसमी",
                  "pa": "ਤਿਉਹਾਰ ਜਾਂ ਮੌਸਮੀ"},
        "desc": {"en": "Tie the ad to a festival or the season.",
                 "hi": "ऐड को त्योहार या मौसम से जोड़ें।",
                 "pa": "ਐਡ ਨੂੰ ਤਿਉਹਾਰ ਜਾਂ ਮੌਸਮ ਨਾਲ ਜੋੜੋ।"},
        "guidance": (
            "FESTIVAL/SEASONAL style: tie the offer to the current festival or season with "
            "a warm, celebratory tone and a natural sense of timeliness. Keep it locally "
            "relevant; do not name a festival unless it fits the audience."
        ),
    },
    "social_proof": {
        "emoji": "⭐",
        "label": {"en": "Trusted by many", "hi": "बहुतों का भरोसा",
                  "pa": "ਬਹੁਤਿਆਂ ਦਾ ਭਰੋਸਾ"},
        "desc": {"en": "Show ratings, happy customers, years in business.",
                 "hi": "रेटिंग, खुश ग्राहक, कितने साल से — दिखाएँ।",
                 "pa": "ਰੇਟਿੰਗ, ਖੁਸ਼ ਗਾਹਕ, ਕਿੰਨੇ ਸਾਲਾਂ ਤੋਂ — ਵਿਖਾਓ।"},
        "guidance": (
            "SOCIAL-PROOF style: lead with credibility — number of happy customers, star "
            "ratings, years in business, or well-known local clients. Reassure a cautious "
            "buyer. Use only claims the brief supports; never fabricate numbers."
        ),
    },
    "problem_solution": {
        "emoji": "💡",
        "label": {"en": "Solve a problem", "hi": "समस्या हल करें",
                  "pa": "ਸਮੱਸਿਆ ਹੱਲ ਕਰੋ"},
        "desc": {"en": "Name the customer's problem, then show your fix.",
                 "hi": "ग्राहक की परेशानी बताएँ, फिर अपना हल दिखाएँ।",
                 "pa": "ਗਾਹਕ ਦੀ ਪਰੇਸ਼ਾਨੀ ਦੱਸੋ, ਫਿਰ ਆਪਣਾ ਹੱਲ ਵਿਖਾਓ।"},
        "guidance": (
            "PROBLEM→SOLUTION style: open by naming the customer's pain in their own words, "
            "then present the business as the clear fix. Empathetic, not preachy."
        ),
    },
    "urgency": {
        "emoji": "⏳",
        "label": {"en": "Limited time or few spots", "hi": "सीमित समय या कम सीटें",
                  "pa": "ਸੀਮਤ ਸਮਾਂ ਜਾਂ ਘੱਟ ਸੀਟਾਂ"},
        "desc": {"en": "Push action now — a deadline or limited seats.",
                 "hi": "अभी कदम उठाने के लिए — डेडलाइन या कम सीटें।",
                 "pa": "ਹੁਣੇ ਕਦਮ ਚੁੱਕਣ ਲਈ — ਡੈੱਡਲਾਈਨ ਜਾਂ ਘੱਟ ਸੀਟਾਂ।"},
        "guidance": (
            "URGENCY style: create a real sense of act-now with a deadline or limited "
            "availability. Must stay truthful — only use scarcity/deadlines the brief "
            "actually supports; never fake it."
        ),
    },
    "question": {
        "emoji": "❓",
        "label": {"en": "Ask a question", "hi": "सवाल पूछें", "pa": "ਸਵਾਲ ਪੁੱਛੋ"},
        "desc": {"en": "Open with a relatable question that hooks them.",
                 "hi": "ऐसा सवाल जो ग्राहक को अपनी बात लगे।",
                 "pa": "ਅਜਿਹਾ ਸਵਾਲ ਜੋ ਗਾਹਕ ਨੂੰ ਆਪਣੀ ਗੱਲ ਲੱਗੇ।"},
        "guidance": (
            "QUESTION style: open with a relatable question the target audience would answer "
            "'yes' to, then resolve it with the offer. Conversational, curiosity-driven."
        ),
    },
}

# The owner-facing "let Saathi decide" option — represented as ad_style=None on the account.
AUTO_STYLE_LABEL = {"en": "Let Saathi choose the best", "hi": "Saathi सबसे अच्छा चुने",
                    "pa": "Saathi ਸਭ ਤੋਂ ਵਧੀਆ ਚੁਣੇ"}
AUTO_STYLE_DESC = {"en": "Recommended — Saathi picks and keeps improving.",
                   "hi": "सुझाव — Saathi चुनकर सुधारता रहेगा।",
                   "pa": "ਸੁਝਾਅ — Saathi ਚੁਣ ਕੇ ਸੁਧਾਰਦਾ ਰਹੇਗਾ।"}


def is_valid_style(key: str | None) -> bool:
    """None ('auto') is valid; any real key must be in the catalog."""
    return key is None or key in AD_STYLES


def style_guidance(key: str | None) -> str:
    """Maker guidance for a chosen style. Empty string for auto → Maker picks freely."""
    if not key:
        return ""
    return AD_STYLES.get(key, {}).get("guidance", "")


def styles_for_locale(locale: str) -> list[dict]:
    """Owner-facing picker options for a locale, 'auto' first (the recommended default)."""
    loc = locale if locale in ("en", "hi", "pa") else "en"
    out = [{
        "key": "auto",
        "emoji": "✨",
        "label": AUTO_STYLE_LABEL[loc],
        "desc": AUTO_STYLE_DESC[loc],
        "recommended": True,
    }]
    for key, s in AD_STYLES.items():
        out.append({
            "key": key,
            "emoji": s["emoji"],
            "label": s["label"][loc],
            "desc": s["desc"][loc],
            "recommended": False,
        })
    return out
