import random

HASH_ICON_COUNT = 7

hashTextEntries = [
    "item-consumable",
    "item-tent",
    "item-key",
    "ability-unequip",
    "weapon-keyblade",
    "weapon-staff",
    "weapon-shield",
    "armor",
    "magic",
    "material",
    "exclamation-mark",
    "question-mark",
    "accessory",
    "party",
    "ai-mode-frequent",
    "ai-mode-moderate",
    "ai-mode-rare",
    "ai-settings",
    "rank-s",
    "rank-a",
    "rank-b",
    "rank-c",
    "gumi-brush",
    "gumi-blueprint",
    "gumi-ship",
    "gumi-block",
    "gumi-gear"
# These were commented out due to the PC and PS2 versions not having matching icons for them
#    "form",
#    "button-r1",
#    "button-r2",
#    "button-l1",
#    "button-l2",
#    "button-triangle",
#    "button-cross",
#    "button-square",
#    "button-circle",
]


def generateHashIcons(local_random: random.Random = None):
    if local_random is None:
        return random.choices(hashTextEntries, k=HASH_ICON_COUNT)
    else:
        return local_random.choices(hashTextEntries, k=HASH_ICON_COUNT)
