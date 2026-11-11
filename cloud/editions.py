"""Per-edition settings shared by the cloud scripts (the reel itself is configured in projects/_radar/run_edition.py)."""
EDITIONS = {
    "egx": {
        "project": "market-radar-daily", "file": "kanz-market-close-cairo-tokyo", "tz": "Africa/Cairo",
        "home": "egx30", "stable_after": (14, 50), "stable_secs": 600, "give_up": (15, 10), "kanz": True,
    },
    "us": {
        "project": "market-radar-europe-us", "file": "kanz-market-close-europe-newyork", "tz": "America/New_York",
        "home": "spx", "stable_after": (16, 5), "stable_secs": 300, "give_up": (16, 30), "kanz": False,  # Kanz has no European indices
    },
}
