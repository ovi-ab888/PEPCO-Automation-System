# ================================================================
#  swingtag_csv/classification.py
#  Item classification / collection niye helper function.
#  (Ported as-is from SS27 classification.py — shudhu import path
#  "constants" -> "enrichment.constants" e change kora hoyeche.)
# ================================================================
from enrichment.constants import COLLECTION_MAPPING


def get_classification_type(item_class):
    """Determine class type key used in COLLECTION_MAPPING."""
    if not item_class:
        return None
    ic = item_class.lower()
    if 'younger girls outerwear' in ic:
        return 'yg'
    if 'older girls outerwear' in ic:
        return 'og'
    if 'younger boys outerwear' in ic:
        return 'yb'
    if 'older boys outerwear' in ic:
        return 'ob'
    if 'baby girls outerwear' in ic:
        return 'a'
    if 'baby boys outerwear' in ic:
        return 'b'
    if 'baby girls essentials' in ic:
        return 'd_girls'
    if 'baby boys essentials' in ic:
        return 'd'
    if 'ladies outerwear' in ic:
        return 'l'
    if 'mens outerwear' in ic:
        return 'm'
    return None


def map_item_class_to_dept_label(item_class):
    """Map item_class text to UI Department names."""
    if not item_class:
        return None
    ic = item_class.lower()
    if 'baby boys outerwear' in ic or 'baby boys essentials' in ic:
        return "Baby Boy"
    if 'baby girls outerwear' in ic or 'baby girls essentials' in ic:
        return "Baby Girl"
    if 'younger boys outerwear' in ic or 'older boys outerwear' in ic:
        return "Boys"
    if 'younger girls outerwear' in ic or 'older girls outerwear' in ic:
        return "Girls"
    if 'ladies outerwear' in ic:
        return "Women"
    if 'mens outerwear' in ic:
        return "Mens"
    return None


def modify_collection(collection, item_class):
    """Append B/G based on gender groups."""
    if not item_class:
        return collection
    ic = item_class.lower()
    if any(x in ic for x in ['younger boys', 'older boys']):
        return f"{collection} B"
    if any(x in ic for x in ['younger girls', 'older girls']):
        return f"{collection} G"
    return collection


def map_collection_name(collection, item_class):
    """COLLECTION_MAPPING theke match kora notun collection name. Na pele ager ta."""
    class_type = get_classification_type(item_class)
    collection = str(collection)
    if class_type and class_type in COLLECTION_MAPPING:
        for orig, new in COLLECTION_MAPPING[class_type].items():
            if orig.upper() in collection.upper():
                return new
    return collection
