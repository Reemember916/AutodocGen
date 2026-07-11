import difflib


def diff_segments(old_seg, new_seg, threshold=0.0):
    old_text = "\n".join(b.text for b in old_seg.blocks)
    new_text = "\n".join(b.text for b in new_seg.blocks)

    if old_text == new_text:
        return None

    r = difflib.SequenceMatcher(None, old_text, new_text, autojunk=False).ratio()
    if 1 - r <= threshold:
        return None

    return {
        "type": "修改",
        "old": old_seg,
        "new": new_seg
    }
