from botstate import BotState
import datastuff


def parse_args(args:str):
    in_quotes = False
    escaped = False
    results = []
    current = ""
    for char in args:
        match char:
            case " ":  # space terminates an arg unless in quotes
                if in_quotes:
                    current = current + " "
                else:
                    if current:  # if there isn't an arg, don't do anything (multiple spaces or spaces at start/end)
                        results.append(current)
                        current = ""
            case "\"":  # quote mark toggles quote status unless escaped
                if escaped:
                    current = current + "\""
                    escaped = False
                else:
                    if in_quotes:
                        in_quotes = False
                    else:
                        in_quotes = True
            case "\\":  # backslash escapes next character, unless it is already escaped
                if escaped:
                    current = current + "\\"
                    escaped = False
                else:
                    escaped = True
            case _:  # anything else, just append
                current = current + char
    if current:  # don't append an empty argument
        results.append(current)
    return results


async def bot_info(args):
    return "Бот версия ХЗ\nВроде работет, отъебись"


async def get_env(args, scope: int):
    env_name = args[0]
    env_value = datastuff.console_get_env(env_name=env_name,chatid=scope)
    env_local = datastuff.console_get_env(env_name=env_name,chatid=scope, option=datastuff.env_var_option.LOCAL)
    if env_value:
        if env_local:
            return "Local environment variable %"+env_name+"% equals to '" + env_value + "'."
        else:
            return "Local environment variable %" + env_name + "% is not set.\r\n"+"Global environment variable %"+env_name+"% equals to '" + env_value + "'."
    else:
        return "Environment variable %" + env_name + "% is not set."


async def get_envx(args):
    env_name = args[0]
    env_value = datastuff.console_get_env(env_name=env_name,chatid=0)
    if env_value:
        return "Global environment variable %"+env_name+"% equals to '" + env_value + "'."
    else:
        return "Global environment variable %" + env_name + "% is not set."


async def set_env(args,scope: int):
    env_name = args[0]
    env_value = args[1]
    datastuff.console_set_env(env_name=env_name,env_value=env_value,scopeid=scope)
    return "Local environment variable %"+env_name+"% has been set to '" + env_value + "'."


async def set_envx(args):
    env_name = args[0]
    env_value = args[1]
    datastuff.console_set_env(env_name=env_name,env_value=env_value,scopeid=0)
    return "Global environment variable %"+env_name+"% has been set to '" + env_value + "'."


async def pool_add(args,chatid: int):  # pool-add "funny messages" -1234567890 "funny_message_11" 2
    pool_id = args[0]
    pool_chatid = args[1]
    message_name = args[2]
    weight = args[3] if len(args) > 3 else 1
    return datastuff.add_message_to_pool(chatid=pool_chatid,name=message_name,pool_id=pool_id,weight=weight)


async def pool_capture_start(args, userid: int,chatid:int):  # pool-capture-start "funny messages" -1234567890
    pool_id = args[0]
    pool_chat_id = args[1] if len(args) > 1 else 0
    # TODO escape " in pool_id =
    command = "pool-add \"" + str(pool_id) + "\" " + str(pool_chat_id)
    cap_mode = "full" 
    if str(pool_chat_id) == "0":
        cap_mode="full-glob"
    sessid = str(chatid) + " " + str(userid)
    context = pool_id
    BotState.DBLink.execute("""
    INSERT INTO message_captures
    VALUES (?,?,?,?)
    """,(sessid,cap_mode,context,command))
    return "Capture mode set for pool '" + pool_id + "'."


async def pool_capture_end(args, userid: int,chatid:int):
    capture = datastuff.console_find_capture(userid=userid, chatid=chatid)
    if not capture:
        return "No capture mode found for current session."
    datastuff.console_end_capture(userid=userid,chatid=chatid)
    return "Capture mode ended."
    pass
