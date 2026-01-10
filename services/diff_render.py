import difflib


def render_side_by_side(unified_diff: str) -> str:
    """
    Minimal side-by-side HTML using difflib.
    """
    left, right = [], []
    for line in unified_diff.splitlines():
        if line.startswith("+") and not line.startswith("+++"):
            right.append(line)
        elif line.startswith("-") and not line.startswith("---"):
            left.append(line)
        else:
            left.append(line)
            right.append(line)

    hd = difflib.HtmlDiff(tabsize=4, wrapcolumn=120)
    return hd.make_table(left, right, fromdesc="Proposed", todesc="After", context=True, numlines=3)
