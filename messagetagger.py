import botstate


class MessageTagger:

    @staticmethod
    def tag_message(chat_id:int, message_id:int, tag:str, *args:str):
        """
        Tags a message
        @param chat_id:
        @param message_id:
        @param tag: tag of the item
        @param args: any additional data, up to 7 items
        @return:
        """
        max7 = args[:7]
        exact7 = max7 + (("",) * (7 - len(max7)))
        botstate.BotState.DBLink.execute("""
        INSERT INTO message_events
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (chat_id,message_id,tag) + exact7)
        botstate.BotState.write()
        print(f"wrote <{chat_id}/{message_id}>, tag: <{tag}> data:<{exact7}>")

    @staticmethod
    def get_tags(chat_id:int, message_id:int) -> dict[str,tuple[str]]:
        """
        Gets tags for a message in a specific chat.
        @param chat_id:
        @param message_id:
        @return:
        """
        res = botstate.BotState.DBLink.execute("""
        SELECT event_type,data0,data1,data2,data3,data4,data5,data6
        FROM message_events
        WHERE chatid = ?
        AND messageid = ?
        """,(chat_id,message_id))
        rows = res.fetchall()
        if not rows:
            return {}
        tags = {}
        for row in rows:
            tag,*data = row
            tags[tag] = data
            print(f"Found: <{chat_id}/{message_id}>, tag: <{tag}> data:<{data}>")
        return tags
