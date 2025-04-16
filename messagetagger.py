import botstate


class MessageTagger:

    @staticmethod
    def tag_message(chat_id:int, message_id:int, tag:str):
        """
        Tags a message
        @param chat_id:
        @param message_id:
        @param tag:
        @return:
        """
        botstate.BotState.DBLink.execute("""
        INSERT INTO message_tags
        VALUES (?, ?, ?)
        """, (chat_id,message_id,tag))
        botstate.BotState.write()

    @staticmethod
    def get_tags(chat_id:int, message_id:int) -> list[str]:
        """
        Gets tags for a message in a specific chat.
        @param chat_id:
        @param message_id:
        @return:
        """
        res = botstate.BotState.DBLink.execute("""
        SELECT tag
        FROM message_tags
        WHERE chat_id = ?
        AND message_id = ?
        """,(chat_id,message_id))
        rows = res.fetchall()
        return [] if not rows else [row[0] for row in rows]