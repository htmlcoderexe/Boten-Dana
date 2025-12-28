
# #TODO: implement all this properly

async def do_console_command(command: string, args,chatid: int, messageid: int,prev:int,userid:int):
    output = "Unrecognised command: "+command+"."
    pargs = console_commands.parse_args(args)
    match command:
        case "info":
            output = await console_commands.bot_info(pargs)
        case "exit":
            datastuff.console_end_session(chatid=chatid,userid=userid,messageid=prev)
            # datastuff.schedule_kill(chatid=chatid,msgid=messageid,expiration=0)
            return
        case "get":
            output = await console_commands.get_env(pargs,chatid)
        case "getx":
            output = await console_commands.get_envx(pargs)
        case "set":
            output = await console_commands.set_env(pargs,chatid)
        case "setx":
            output = await console_commands.set_envx(pargs)
        case "pool-add":
            output = await console_commands.pool_add(pargs,chatid)
        case "pool-capture-begin":
            output = await console_commands.pool_capture_start(pargs,userid,chatid)
        case "pool-capture-end":
            output = await console_commands.pool_capture_end(pargs,userid,chatid)
    output = "<pre>\nUser#&gt; "+command+" "+args+"\nDanaBot#&gt; "+output+"\n</pre>"
    await datastuff.console_spawn(chatid=chatid,userid=userid,source=messageid,text=output,previous=prev)
    pass


async def do_console_command_direct(command: string, args,chatid: int, userid:int):
    output = "Unrecognised command: "+command+"."
    pargs = console_commands.parse_args(args)
    match command:
        case "info":
            output = await console_commands.bot_info(pargs)
        case "get":
            output = await console_commands.get_env(pargs,chatid)
        case "getx":
            output = await console_commands.get_envx(pargs)
        case "set":
            output = await console_commands.set_env(pargs,chatid)
        case "setx":
            output = await console_commands.set_envx(pargs)
    output = "<pre>\nUser#&gt; "+command+" "+args+"\nDanaBot#&gt; "+output+"\n</pre>"
    pass


async def console_capture_message(userid: int, chatid: int, msg: Message):
    capture = datastuff.console_find_capture(userid=userid, chatid=chatid)
    if not capture:
        return False
    mode, context, commandline = capture
    commandline_split = commandline.split()
    command = commandline_split[0]
    args = " ".join(commandline_split[1:])
    match mode:
        case "full":
            msgname = str(chatid)+" " + str(userid) + " " + context + " " + str(msg.id)
            # await datastuff.save_message(name=msgname,msg=msg,userid=userid,chatid=chatid)
            args = args + " \"" + msgname + "\""
            prev, mode = datastuff.console_find_latest_session(chatid=chatid,userid=userid)
            await do_console_command(command=command,args=args,chatid=chatid,userid=userid,messageid=0,prev=prev)
        case "full-glob":
            msgname = str(chatid)+" " + str(userid) + " " + context + " " + str(msg.id)
            # await datastuff.save_message(name=msgname,msg=msg,userid=userid,chatid=0)
            args = args + " \"" + msgname + "\""
            prev, mode = datastuff.console_find_latest_session(chatid=chatid,userid=userid)
            await do_console_command(command=command,args=args,chatid=chatid,userid=userid,messageid=0,prev=prev)