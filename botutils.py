import io

from telegram.helpers import escape_markdown


def print_to_string(*args, **kwargs):
    output = io.StringIO()
    print(*args, file=output, **kwargs)
    contents = output.getvalue()
    output.close()
    return contents


def MD(text_input: str,version: int = 2) -> str:
    """Shortcut to escape MarkDown"""
    return escape_markdown(text=text_input, version=version)


def S(text_input: str) -> str:
    """Strips punctuation and trailing/leading whitespace"""
    t = text_input.maketrans("", "", ".,!:;\\/\"'?")
    s = text_input.translate(t)
    s = s.strip()
    return s


def TU(usertag: str, userid: int) -> str:
    """Generates markup to tag a specific user with a specific text"""
    return f" [{usertag}](tg://user?id={userid}) "


def md_safe_int(number: int) -> str:
    if number < 0:
        return "\\-" + str(number.__abs__())
    return str(number)
