import io
import time

import botstate
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


def schedule_kill(chatid: int, msgid: int, expiration: float):
    """
    Schedules a message to be deleted.
    @param chatid: Chat ID where to delete the message.
    @param msgid: Message ID to delete.
    @param expiration: Time in seconds from current moment when the message is to be deleted.
    @return:
    """
    if expiration == -1:
        return
    botstate.BotState.DBLink.execute("""
    INSERT INTO msgkills
    VALUES (?,?,?)
    """,
                            (chatid, msgid, time.time() + expiration)
                            )
    botstate.BotState.write()
    print(f"scheduled to kill message {msgid}")


def cancel_kill(chatid: int, msgid: int):
    """
    Cancels a scheduled message deletion.
    @param chatid: Chat ID
    @param msgid: Message ID to cancel deletion of.
    @return:
    """
    botstate.BotState.DBLink.execute("DELETE from msgkills WHERE chatid=? AND msgid = ?", (chatid, msgid))
    botstate.BotState.write()
    print(f"canceled message kill for {msgid}")
