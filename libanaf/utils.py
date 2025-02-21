def sanitize_file_name(*dirty, glue: str = "_", replace_char: str = "-") -> str:
    """
    Cleans and concatenates multiple string parts to form a valid filename or identifier.

    This function takes any number of string arguments (`dirty`) and returns a single
    string by:
    1. Stripping leading and trailing whitespace.
    2. Removing all literal periods ('.').
    3. Replacing invalid and special characters (e.g. /, \\, ?, &, :, etc.) with
    the `replace_char`.
    4. Collapsing consecutive instances of `replace_char` into a single instance.
    5. Joining all parts together using the `glue` string.

    Args:
        *dirty: One or more string components to be sanitized and concatenated.
        glue (str, optional): The character(s) used to join the sanitized parts. Defaults to '_'.
        replace_char (str, optional): The character used to replace invalid or special characters. Defaults to '-'.

    Returns:
        str: The sanitized, joined string suitable for use as a filename or similar identifier.

    Example:
        >>> self._sanitize_file_name(' My/Document ', 'v.1 ', glue='-', replace_char='!')
        'My!Document-v!1'
    """
    import re

    parts: list[str] = list()
    for part in dirty:
        part = part.strip().replace(".", "")
        # part = re.sub(r"[[:space]]", replace_char, part)
        part = re.sub(r"[/\\?`&%*:|\"<>\x7F\x00-\x1F,.\s]", replace_char, part)
        pattern = replace_char + "+"
        part = re.sub(pattern, replace_char, part)

        parts.append(part)

    # dirty = dirty.strip().replace('.', '')
    # clean: str = re.sub(r"[/\\?%*:|\"<>\x7F\x00-\x1F.]\*", "-", dirty.strip())

    return glue.join(parts)
