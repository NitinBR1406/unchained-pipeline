"""Reusable brand profile + presentation presets (config, not hardcoded per song)."""

UNCHAINED_NITIN_BRAND_PROFILE_V1 = {
    "id": "UNCHAINED_NITIN_BRAND_PROFILE_V1",
    "artist": "UNCHAINED NITIN",
    "tagline": "THE INDESTRUCTIBLE VOICE",
    "positioning": "A WESTERN SOUND WITH EASTERN SOUL",
    "visual_direction": "deep matte black; premium antique/polished gold; cinematic studio",
    "colors": {"gold": "#D4AF37", "cream": "#F0EAD6", "sand": "#C5A059", "white": "#F8F8F6"},
    "typography": {"display": "Cinzel SemiBold", "body": "Montserrat"},
    "monogram": "official UN chain monogram",
    "rule": "PERFORMER FACE PRIORITY > BRAND GRAPHICS",
    "obscure_forbidden": ["eyes", "face", "expression"],
}

PRESENTATION_PRESETS = {
    "MOTION_A_PREMIUM_RESTRAINED": {
        "id": "MOTION_A_PREMIUM_RESTRAINED",
        "locked": True,
        "cinematic_push_ceiling": 1.04,
        "shake_px_strong": 19,
        "impact_flash_opacity": 0.25,
        "notes": "Locked baseline. Selective motion only; no continuous zoom.",
    },
    "MOTION_B_PREMIUM_ROCK": {
        "id": "MOTION_B_PREMIUM_ROCK",
        "locked": False,
        "cinematic_push_ceiling": 1.08,
        "shake_px_strong": 30,
        "impact_flash_opacity": 0.35,
        "notes": "Optional stronger preset. Never auto-selected; campaign must request it.",
    },
}


def get_preset(name):
    if name not in PRESENTATION_PRESETS:
        raise KeyError(f"unknown presentation preset: {name}")
    return PRESENTATION_PRESETS[name]
