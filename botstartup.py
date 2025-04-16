from botstate import BotState


def assert_table(name: str, columns, primary_key=None):
    print(name)
    headers = []
    if primary_key:
        for column in columns:
            if column == primary_key:
                headers.append(column + " INTEGER PRIMARY KEY ASC")
            else:
                headers.append(column)
    else:
        headers = list(columns)
    query = f"CREATE TABLE {name}(" +" , ".join(headers) + ")"
    res = BotState.DBLink.execute("SELECT name FROM sqlite_master WHERE name=?", (name,))
    if res.fetchone() is None:
        BotState.DBLink.execute(query)
        BotState.write()
        print(f"Created table \"{name}\" with fields {columns}.")
    else:
        print(f"Table \"{name}\" already exists.")


assert_table("repuser", ("chatid","userid", "rep","msg"))
assert_table("userseen",("chatid","userid","last","lastunreg","emoji"))
assert_table("user_events",("chatid","userid","time","event_type","event_data"))
assert_table("join_dates",("chatid","userid","time","fake"))
assert_table("user_info",("chatid","userid","nick","pronouns"))
assert_table("qdb",("qid","chatid","userid","author","messageid","quote","reply_id","reply_text","reply_user","rating"),"qid")
assert_table("msgkills",("chatid","msgid","expiration"))
assert_table("unsubscribers",("userid",))
assert_table("perms",("chatid","userid","perm"))
assert_table("scores",("chatid","userid","scorename","scope","amount"))
assert_table("changelogs",("logid",))
assert_table("saved_messages",("chatid","name","type","data","userid","time"))
assert_table("records",("userid","chatid","valuename","valueamount","source_message"))
assert_table("quizzes",("ownerid","created","title","question_time","name"))
assert_table("quiz_questions",("quiz_name","question_text","ordinal","options","correct_option","extraid"))
assert_table("quiz_replytracker",("quiz_session_id","pollid","quiz_name","ordinal","time","msgid"))
assert_table("quiz_scores",("quiz_session_id","quiz_name","userid","seconds","answers"))
assert_table("quiz_next",("quiz_session_id","chatid","time","quiz_name","ordinal"))
assert_table("quiz_sessions",("quiz_session_id","chatid","start_message_id"))
assert_table("edit_sessions",("session_name","userid"))
assert_table("message_lists",("list_id","userid","chatid","message_name","weight"))
assert_table("console_sessions",("chatid","starttime","last_active","endtime","userid","messageid","mode"))
assert_table("global_config",("setting_name","setting_value"))
assert_table("local_config",("chatid","setting_name","setting_value"))
assert_table("message_pools",("pool_id","chatid","message_name","weight"))
assert_table("console_confirms",("session_id","prev_command"))
assert_table("env_vars",("var_name","var_value","var_scope"))
assert_table("message_captures", ("session_id","capture_mode","context_id","capture_command"))
assert_table("message_events",("chatid","messageid","event_type","data0","data1","data2","data3","data4","data5","data6"))
