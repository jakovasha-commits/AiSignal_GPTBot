FLAG = {
    "USD": "🇺🇸",
    "EUR": "🇪🇺",
    "GBP": "🇬🇧",
    "JPY": "🇯🇵",
    "CHF": "🇨🇭",
    "AUD": "🇦🇺",
    "CAD": "🇨🇦",
    "NZD": "🇳🇿",
}

def pretty_pair(pair: str, otc: bool) -> str:
    base, quote = pair.split("/")
    base_f = FLAG.get(base, "")
    quote_f = FLAG.get(quote, "")
    suffix = " OTC" if otc else ""
    return f"{base_f}/{quote_f} {pair}{suffix}".strip()
