from botstate import BotState


class Quiz:
    id = 0

    def __init__(self, quizid):
        self.id = quizid

    def rename(self, newname: str):
        BotState.DBLink.execute("""
                UPDATE quizzes
                SET title = ?
                WHERE name = ?""", (newname, self.id))
        BotState.write()

    def set_time(self, newtime:int):
        BotState.DBLink.execute("""
                UPDATE quizzes
                SET question_time = ?
                WHERE name = ?""", (newtime, self.id))
        BotState.write()
