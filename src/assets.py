import json


def normalize_asset_name(
    candidate: str,
    known_assets: set[str],
    api_key: str,
) -> tuple[str, bool]:
    """Match candidate against known assets, using LLM for fuzzy matching.

    Returns (final_name, was_corrected).
    """
    # Exact match → no LLM call needed
    if candidate in known_assets:
        return candidate, False

    # No known assets yet → first asset, just register it
    if not known_assets:
        return candidate, False

    # Fuzzy match via LLM
    from .llm import call_openrouter_text

    prompt = (
        "You are an asset name matcher. Given a candidate name and a list of known names, "
        "determine if the candidate is a typo/variant of one of the known names.\n\n"
        f"Candidate: \"{candidate}\"\n"
        f"Known names: {json.dumps(sorted(known_assets), ensure_ascii=False)}\n\n"
        "If the candidate matches one of the known names (typo, minor variation, "
        "different casing, missing/extra word), respond with ONLY the exact known name.\n"
        "If it's a genuinely new/different asset, respond with ONLY the word: NEW\n"
        "No explanation, no quotes, just the name or NEW."
    )

    result = call_openrouter_text(prompt, api_key).strip().strip('"')

    if result == "NEW" or result not in known_assets:
        return candidate, False

    return result, True
