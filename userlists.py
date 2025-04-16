import botstate


class UserList:

    @staticmethod
    def check_list(user_id:int,list_name:str):
        res = botstate.BotState.DBLink.execute("""
        SELECT user_id FROM user_lists
        WHERE user_id = ?
        AND list_name = ?
        """,(user_id,list_name))
        row = res.fetchone()
        return True if row else False

    @staticmethod
    def add_user(user_id:int, list_name:str):
        if not UserList.check_list(user_id,list_name):
            botstate.BotState.DBLink.execute("""
            INSERT INTO user_lists
            VALUES (?, ?)
            """,(list_name,user_id))
            botstate.BotState.write()

    @staticmethod
    def remove_user(user_id:int, list_name:str):
        if UserList.check_list(user_id,list_name):
            botstate.BotState.DBLink.execute("""
            DELETE FROM user_lists
            WHERE user_id = ?
            AND list_name = ?
            """,(user_id,list_name))
            botstate.BotState.write()
