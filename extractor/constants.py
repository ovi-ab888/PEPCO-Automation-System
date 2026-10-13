"""
extractor/constants.py
Sticker-data mappings — ported unchanged from the old extractor.py /
PEPCO_Data_Extractor constants.py (only the mappings this label engine
actually uses; WASHING_CODES / COLLECTION_MAPPING live in the other
(SS27 CSV) project and aren't needed here).
"""

PICTOGRAM_MAPPING = {
    "PIC00033": "A", "PIC00019": "8", "PIC00020": "9", "PIC00034": "B", "PIC00009": "R",
    "PIC00182": "3", "PIC00181": "5", "PIC00028": "S", "PIC00032": "C", "PIC00010": "Q",
    "PIC00178": "1", "PIC00014": "L", "PIC00011": "N", "PIC00183": "4", "PIC00186": "7",
    "PIC00184": "2", "PIC00012": "M", "PIC00031": "E", "PIC00029": "F", "PIC00027": "G",
    "PIC00185": "6", "PIC00013": "O", "PIC00180": "0", "PIC00030": "D",
}

PROMOTIONAL_MAPPING = {"PROMO": "P", "KVI": "K", "HS": "H"}
