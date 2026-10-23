"""Project-wide configuration for the Steam ingestion."""

# Steam App IDs of the games published by Paradox Interactive (81 apps).
# The IDs come from summaries of Steam's publisher search page, so we verify
# them against the `name` and `publishers` columns after the first load.
GAME_APPIDS = [
    1158310, 3493540, 394360, 281990, 949230, 529340, 1669000, 236850, 3450310, 255710,
    3215050, 233450, 1385380, 203770, 604540, 532790, 637090, 1324130, 859580, 983870,
    346940, 234650, 300550, 362960, 238370, 42960, 1167750, 684450, 1268590, 42910,
    718850, 25800, 226840, 42810, 672630, 25990, 22130, 310060, 231740, 25890,
    73170, 73010, 25830, 1622900, 61520, 234390, 42890, 393430, 42850, 25980,
    61510, 203630, 61500, 205990, 25808, 73210, 227760, 200370, 204940, 355010,
    73020, 225420, 24400, 24480, 42990, 384490, 202130, 42980, 249190, 23420,
    42920, 24410, 616240, 349790, 794820, 24460, 42900, 1257610, 4920230, 1579420,
    1573550,
]  # fmt: skip

# Store prices for Sweden (Steam prices Sweden in EUR) and English text.
STORE_COUNTRY = "se"
STORE_LANGUAGE = "english"

# Seconds to wait between requests. Valve publishes no limit for the Store
# endpoints, so we stay well below the ~1 request/second people report as safe.
REQUEST_PAUSE_SECONDS = 2.0
