from packaging import version


def version_delta(current, latest):
    """
    Returns an integer representing how far behind the current version is.
    If non-semver or invalid, returns None.

    Scale (by your design):
    - Major difference → abs(major delta) * 10
    - Minor difference → abs(minor delta)
    - Patch difference → abs(patch delta)
    """
    if not current or not latest:
        return None

    try:
        c = version.parse(current)
        l = version.parse(latest)

        # If either is not a Version object (e.g. 'latest', 'nightly')
        if not isinstance(c, version.Version) or not isinstance(l, version.Version):
            return None

        # Major difference
        if c.major != l.major:
            return abs(l.major - c.major) * 100

        # Minor difference
        if c.minor != l.minor:
            return abs(l.minor - c.minor) * 10

        # Patch difference
        return abs(l.micro - c.micro)

    except Exception:
        return None
