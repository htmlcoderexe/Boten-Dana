import time

import UserInfo
import actions
import botutils
import messagestore
import scheduled_events
import scores
from actions import TriggeredAction
from telegram import Message as TGMessage
from botstate import BotState
from edit_sessions import EditSession


class Question:
    """Represents a single Quiz question"""
    @classmethod
    def fetch(cls, quizid:str,index:int):
        """Fetches a specific question from a quiz
        @param quizid: ID of the quiz
        @param index: number of the question
        """
        res = BotState.DBLink.execute("""
            SELECT question,options,correct_option,extraid
            FROM quiz_questions
            WHERE quiz_name = ?
            AND ordinal = ?""", (quizid, index))
        row = res.fetchone()
        if not row:
            return
        text, options, correct, extra_id = row
        return cls(quizid,index,text,options.split("|"),correct,extra_id)

    def __init__(self, quiz_id:str, index:int, text:str, choices:list[str], correct:int, attachment:str):
        self.parent_quiz = quiz_id
        """Quiz this belongs to"""
        self.index = index
        """Number of the question"""
        self.text = text
        """Question text"""
        self.choices = choices
        """Question answers"""
        self.correct_answer = correct
        """Number of the correct option"""
        self.attachment = attachment
        """Saved Message ID attached to the question"""
        self.attachment_emoji =""
        """Attachment type emoji, set by the quiz when loaded."""

    def attach_media(self, mediaid:str):
        """Attaches a specific Saved Message to this question"""
        BotState.DBLink.execute("""
            UPDATE quiz_questions
            SET extraid = ?
            WHERE quiz_name = ?
            AND ordinal = ?""", (mediaid, self.parent_quiz, self.index))
        BotState.write()
        self.attachment = mediaid


class Quiz:
    """Represents a Quiz"""
    def __init__(self, quiz_id:str, owner_id:int,created:float,title:str,question_time:float,questions:list[Question]):
        self.id:str = quiz_id
        """This Quiz's ID."""
        self.owner_id:int = owner_id
        """Quiz creator UID"""
        self.creation_time:float = created
        """Quiz creation timestamp"""
        self.title:str = title
        """Title of the quiz"""
        self.question_time:float = question_time
        """Time to answer a question, in seconds"""
        self.questions:list[Question] = questions
        """Questions belonging to the quiz"""
        self.count = len(questions)
        """amount of questions"""
        self.questions_in_mv2 = []
        """Questions in a nice to display list with MarkDownV2 escaping."""
        for question in self.questions:
            index = question.index + 1
            text = botutils.MD(question.text)
            emoji = question.attachment_emoji
            self.questions_in_mv2.append((index, emoji, text))

    @classmethod
    def load(cls, quizid:str):
        res = BotState.DBLink.execute("""
            SELECT ownerid,created,title,question_time
            FROM quizzes
            WHERE name = ?
            """, (quizid,))
        row = res.fetchone()
        if not row:
            return
        owner_id = int(row[0])
        creation_time = float(row[1])
        title = row[2]
        question_time = float(row[3])
        # fetch the questions
        res = BotState.DBLink.execute("""
            SELECT quiz_name, ordinal, question, options, correct_option, extraid
            FROM quiz_questions
            WHERE quiz_name = ?
            ORDER BY ordinal ASC
            """, (quizid,))
        rows = res.fetchall()
        qlist = []
        if rows:
            ms = messagestore.MessageStore(owner_id, owner_id)
            for row in rows:
                qdata = list(row)
                qdata[1] = int(qdata[1])
                qdata[3] = qdata[3].split("|")
                q = Question(*qdata)
                q.attachment_emoji = ms.get_type_emoji(q.attachment)
                qlist.append(q)

        return cls(quizid,owner_id,creation_time,title,question_time,qlist)

    @classmethod
    def create(cls, creator:int, quiz_id:str, title:str, timeout:int):
        """
        The quiz will be created.
        @param creator:
        @param quiz_id:
        @param title:
        @param timeout:
        @return:
        """
        quiz = cls.load(quiz_id)
        if quiz:
            return None
        BotState.DBLink.execute("""
        INSERT INTO quizzes
        VALUES (?,?,?,?,?)
        """, (creator, time.time(), title, timeout, quiz_id))
        BotState.write()
        return cls.load(quiz_id)

    @staticmethod
    def find_by_owner(owner_id:int) -> list[str]:
        """
        Finds all Quizes owned by a user.
        @param owner_id: User to check.
        @return: List of Quiz IDs found.
        """
        res = BotState.DBLink.execute("""
           SELECT title,name
           FROM quizzes
           WHERE ownerid = ?
           """, (owner_id,))
        rows = res.fetchall()
        if not rows:
            return []
        return [row[0] for row in rows]

    def rename(self, newname: str):
        """Renames the Quiz"""
        BotState.DBLink.execute("""
                UPDATE quizzes
                SET title = ?
                WHERE name = ?""", (newname, self.id))
        BotState.write()
        self.title = newname

    def set_time(self, newtime:int):
        """Sets the question timer on the Quiz"""
        BotState.DBLink.execute("""
                UPDATE quizzes
                SET question_time = ?
                WHERE name = ?""", (newtime, self.id))
        BotState.write()
        self.question_time = newtime

    def add_question(self, question:Question, index:int = -1) -> int:
        """Adds a Question to the Quiz
        @param question: The Question to be added.
        @param index: Optional index to insert the question at. This will renumber the questions after it.
        """
        # easy case with adding on the end
        if index == -1 or index >= len(self.questions):
            BotState.DBLink.execute("""
                INSERT INTO quiz_questions
                VALUES (?,?,?,?,?,?)
                """, (self.id, question.text,
                      len(self.questions), "|".join(question.choices),
                      question.correct_answer, question.attachment))
            BotState.write()
            self.questions.append(question)
            return len(self.questions) - 1
        # update the question indices in the DB
        BotState.DBLink.execute("""
        UPDATE quiz_questions
        SET ordinal = ordinal + 1
        WHERE quiz_name = ?
        AND ordinal >= ?
        """,(self.id, index))
        BotState.write()
        # insert the question
        BotState.DBLink.execute("""
            INSERT INTO quiz_questions
            VALUES (?,?,?,?,?,?)
            """, (self.id, question.text,
                  index, "|".join(question.choices),
                  question.correct_answer, question.attachment))
        # update this object
        self.questions.insert(index,question)
        # update question indices in this object
        for ordinal, question in enumerate(self.questions):
            question.index = ordinal
        return index

    def replace_question(self, question:Question, index:int) -> bool:
        """
        Replaces a specific question.
        @param question: Replacement
        @param index: Index to replace
        @return: True on success, False on failure
        """
        if not 0 <= index < len(self.questions):
            return False
        BotState.DBLink.execute("""
            DELETE FROM quiz_questions
            WHERE quiz_name = ?
            AND ordinal = ?""", (self.id, index))
        BotState.DBLink.execute("""
            INSERT INTO quiz_questions
            VALUES (?,?,?,?,?,?)
            """, (self.id, question.text,
                  index, "|".join(question.choices),
                  question.correct_answer, question.attachment))
        self.questions[index] = question
        return True

    def remove_question(self, index:int):
        """
        Removes a question at the specific index.
        @param index: Number of the question to remove
        @return:
        """
        # -1 removes last question
        if index == -1:
            index = self.count - 1
        # erase question from DB
        BotState.DBLink.execute("""
        DELETE FROM quiz_questions
        WHERE quiz_name = ?
        AND ordinal = ?""",(self.id, index))
        # update indices in DB
        BotState.DBLink.execute("""
            UPDATE quiz_questions
            SET ordinal = ordinal - 1
            WHERE quiz_name = ?
            AND ordinal > ?
            """, (self.id, index))
        # update this object
        self.questions.pop(index)
        # update question indices in this object
        for ordinal, question in enumerate(self.questions):
            question.index = ordinal


class QuizPlaySession:
    """Represents a single run of a Quiz."""
    START_MESSAGE_ANIMATION_TIMER: float = 3
    MEDAL_EMOJI: list[str] = ["🥇", "🥈", "🥉"]
    """Time delay used between edits"""
    @classmethod
    def load(cls, session_id: str):
        """
        Loads a session from the database
        @param session_id: The session to load
        @return:
        """
        # TODO: modify the table schema of quiz_sessions and quiz_replytracker
        res = BotState.DBLink.execute("""
            SELECT quiz_session_id,chatid,quiz_id,start_message_id,ended
            FROM quiz_sessions
            WHERE quiz_session_id = ?""", (session_id,))
        row = res.fetchone()
        if not row:
            return None
        return cls(*row)

    @classmethod
    def start(cls, quiz_id: str, chat_id: int, start_message: int):
        now = time.time()
        # create session ID
        session_id = str(chat_id) + quiz_id + str(now)
        # write to DB
        BotState.DBLink.execute("""
            INSERT INTO quiz_sessions
            VALUES (?,?,?,?,0)""", (session_id, chat_id, quiz_id, start_message))
        BotState.write()
        # return session object
        return cls(session_id, chat_id, quiz_id, start_message, False)

    @staticmethod
    def check_ongoing(chat_id: int) -> bool:
        """
        Checks if a chat has an unfinished session.
        @param chat_id: Chat ID to check
        @return: A bool indicating whether an unfinished session was found.
        """
        res = BotState.DBLink.execute("""
            SELECT ended
            FROM quiz_sessions
            WHERE chatid = ?
            AND ended = 0""", (chat_id,))
        rows = res.fetchall()
        if rows:
            return True
        return False

    @staticmethod
    def submit_answer(poll_id:int, user_id:int, option_picked:int):
        """
        Processes a poll asnwer
        @param poll_id: PollID the answer comes from
        @param user_id: User that sent the answer
        @param option_picked: The answer option picked
        @return:
        """
        # put down time
        now = time.time()
        # find the corresponding tracker
        res = BotState.DBLink.execute("""
            SELECT quiz_session_id, quiz_name,ordinal,time,msgid
            FROM quiz_replytracker
            WHERE pollid = ?""", (str(poll_id),))
        row = res.fetchone()
        # exit if not found
        if not row:
            return
        session_id, quiz_id, question_number, poll_time, poll_msgid = row
        session = QuizPlaySession.load(session_id)
        # fetch the question
        question = Question.fetch(quiz_id, question_number)
        # exit if not found
        if not question:
            return
        # on a correct answer, record this
        if option_picked == question.correct_answer:
            diff = now - poll_time
            session.award_correct_answer(user_id, diff)
        # on a single player session, advance immediately to the next question
        if session.singleplayer:
            next_question = question_number + 1
            botutils.schedule_kill(session.chat_id, poll_msgid, 0)
            BotState.DBLink.execute(("""
                    UPDATE quiz_next
                    SET time = 0
                    WHERE quiz_session_id = ?
                    AND ordinal = ?
                    """), (session_id, next_question))
            BotState.write()

    def __init__(self, session_id: str, chat_id: int, quiz_id: str, starting_message: int, ended: bool):
        self.id = session_id
        """Session ID"""
        self.chat_id = chat_id
        """Chat running the session"""
        self.singleplayer = chat_id > 0
        """Determines whether this session is run in a private chat with one person or in a chat with multiple people."""
        self.quiz_id = quiz_id
        """The Quiz used in the session"""
        self.start_message = starting_message
        """MessageID of the message launching the session"""
        self.ended = ended
        """Determines if the session has ended."""

    def write_plan(self, question_count: int, question_timer: float, frame_count: int):
        """Writes out the commands to follow for the quiz runner
        @param question_count: amount of questions
        @param question_timer: time given per question
        @param frame_count: amount of animation frames
        """
        # set starting point
        now = time.time()
        # this will hold the items to be written to the DB
        plan = []
        # 2 message edits #TODO make this more flexible somehow?
        for i in range(-frame_count, 0, 1):
            now += QuizPlaySession.START_MESSAGE_ANIMATION_TIMER
            plan.append((now, i))
        now += QuizPlaySession.START_MESSAGE_ANIMATION_TIMER
        # the questions
        for index in range(question_count):
            plan.append((now,index))
            now += question_timer
        # final item to finish the quiz
        plan.append((now, question_count))
        # write to DB
        for entry in plan:
            moment, command = entry
            scheduled_events.ScheduledEvent.schedule_event("quiz_next", self.chat_id, moment, self.id, self.quiz_id, command)

    def award_correct_answer(self, user_id:int, seconds:float):
        """
        Scores a correct answer in this session.
        @param user_id: User to receive score
        @param seconds: Seconds to add to user's time score
        @return:
        """
        res = BotState.DBLink.execute("""
            SELECT seconds,answers
            FROM quiz_scores
            WHERE quiz_session_id = ?
            AND quiz_name = ?
            AND userid = ?""", (self.id, self.quiz_id, user_id))
        row = res.fetchone()
        if row:
            secs, score = row
            secs += seconds
            score += 1
            BotState.DBLink.execute("""
                UPDATE quiz_scores
                SET seconds = ?,answers = ?
                WHERE quiz_session_id = ?
                AND quiz_name = ?
                AND userid = ?""", (secs, score, self.id, self.quiz_id, user_id))
        else:
            BotState.DBLink.execute("""
                INSERT INTO quiz_scores
                VALUES (?,?,?,?,?)""", (self.id, self.quiz_id, user_id, seconds, 1,))
        BotState.write()

    def get_results(self) -> list:
        """
        Fetches results of this session.
        @return: list of (medal, uid, seconds, correct answers)
        """
        res = BotState.DBLink.execute("""
            SELECT userid,seconds,answers
            FROM quiz_scores
            WHERE quiz_session_id = ?
            ORDER BY answers DESC,seconds""", (self.id,))
        db_results = res.fetchall()
        results = []
        for i, result in enumerate(db_results):
            userid, seconds, answers = result
            seconds = int(seconds)
            usr = UserInfo.User(userid, self.chat_id)
            uname = usr.current_nick
            if i < len(QuizPlaySession.MEDAL_EMOJI):
                results.append((QuizPlaySession.MEDAL_EMOJI[i],uname, seconds, answers))
            else:
                results.append((" ",uname, seconds, answers))
        return results

    def give_awards(self):
        """
        Processes the session's results and awards medal and other scores.
        @return: Returns the results that were processed.
        """
        results = self.get_results()
        for i,result in enumerate(results):
            sh = scores.ScoreHelper(result[1],self.chat_id)
            if i >= len(QuizPlaySession.MEDAL_EMOJI):
                sh.add("quiz_medals_other")
            sh.add("quiz_medals_" + str(i))
            sh.add("quiz_participations")
        return results

    def end(self):
        """
        Ends the session.
        @return:
        """
        BotState.DBLink.execute("""
            UPDATE quiz_sessions
            SET ended = ?
            WHERE quiz_session_id = ?""", (1, self.id))
        botutils.schedule_kill(self.chat_id, self.start_message, 0)

##############################
#   Running
##############################


class TryStartQuiz(TriggeredAction, action_name="quiz_check_clear"):
    """Checks if a quiz may be launched
    param 0: quiz id
    param 1: out result
    """

    async def run_action(self, message: TGMessage) -> str:
        quiz_id = self.read_param(0)
        chat_id = message.chat_id
        if QuizPlaySession.check_ongoing(chat_id):
            self.write_param(1, "quiz_ongoing")
            return ""
        quiz = Quiz.load(quiz_id)
        if not quiz:
            self.write_param(1, "quiz_not_found")
            return ""
        self.write_param(1, "ok")
        return ""


class RunQuiz(TriggeredAction, action_name="quiz_begin"):
    """Begins a quiz.
    param 0: quiz id
    param 1: starting message ID
    """

    async def run_action(self, message: TGMessage) -> str:
        quiz_id = self.read_param(0)
        starting_message = self.read_int(1)

        chat_id = message.chat_id
        quiz = Quiz.load(quiz_id)
        session = QuizPlaySession.start(quiz_id, chat_id, starting_message)
        frame_count = len(actions.TriggeredSequence.running_sequences[self.sequence].strings["start_animation"]) -1
        session.write_plan(len(quiz.questions), quiz.question_time, frame_count)
        return ""


class FetchEvents(TriggeredAction, action_name="quiz_get_plan"):
    """Fetches quiz runner commands.
    param 0: variable to store the events in.
    """
    async def run_action(self, message: TGMessage) -> str:
        outvar = self.read_param(0)
        events = []
        now = time.time()
        res = BotState.DBLink.execute("""
            SELECT quiz_session_id,chatid,time,quiz_name,ordinal
            FROM quiz_next
            WHERE time < ?""", (now,))
        events = res.fetchall()
        self.varstore[outvar] = events
        BotState.DBLink.execute("""
            DELETE
            FROM quiz_next
            WHERE time < ?""", (now,))
        return ""


class RegisterPoll(TriggeredAction, action_name="quiz_register_poll"):
    """
    Associates a specific Poll with a specific Question in a Session.
    param 0: session ID
    param 1: poll ID
    param 2: question number
    """
    async def run_action(self, message: TGMessage) -> str:
        sid = self.read_param(0)
        poll_id = self.read_param(1)
        idx = self.read_param(2)
        session = QuizPlaySession.load(sid)
        BotState.DBLink.execute("""
            INSERT INTO quiz_replytracker
            VALUES (?,?,?,?,?,?)""", (sid, poll_id, session.quiz_id, idx, time.time(), self.varstore["__last_msg"]))
        BotState.write()
        return ""


class ProcessEvent(TriggeredAction, action_name="quiz_do_plan"):
    """Processes a single event.
    param 0: variable storing the event.
    param 1: variable to store the command type
    param 2: variable to store modified event
    param 3: variable to store session
    """
    async def run_action(self, message: TGMessage) -> str:
        event:scheduled_events.ScheduledEvent = self.varstore[self.read_param(0)]
        if not event:
            return ""
        sid = event.event_data[0]
        quiz_id = event.event_data[1]
        cmd = event.event_data[2]
        # store the session
        self.write_param(3,QuizPlaySession.load(sid))
        # negative numbers animate the starting message
        if cmd < 0:
            self.write_param(1,"start_animation")
            self.write_param(2,int(cmd) * -1)
            return ""
        # numbers past the last question end the quiz
        quiz = Quiz.load(quiz_id)
        if cmd >= len(quiz.questions):
            self.write_param(1,"quiz_finish")
            self.write_param(2,0)
            return ""
        # any others should post the question
        self.write_param(1,"question")
        self.write_param(2,cmd)
        return ""


class FinishQuiz(TriggeredAction, action_name="quiz_finish"):
    """
    Finishes up a quiz session.
    param 0: session ID
    param 1: variable to store the results
    """
    async def run_action(self, message: TGMessage) -> str:
        sid = self.read_param(0)
        out_var = self.read_param(1)
        # load the session
        session = QuizPlaySession.load(sid)
        # fetch the results and award medals
        quiz_results = session.give_awards()
        self.varstore[out_var] = quiz_results
        session.end()
        return ""

##################################
#   Access methods
##################################


class FetchQuestion(TriggeredAction, action_name="quiz_fetch_question"):
    """
    Fetches a single question.
    param 0: Quiz ID
    param 1: Question number
    param 2: Variable to store the retrieved question
    """
    async def run_action(self, message: TGMessage) -> str:
        qid = self.read_param(0)
        idx = self.read_param(1)
        out_var = self.read_param(2)
        # get the question
        question = Question.fetch(qid,idx)
        self.varstore[out_var] = question
        return ""


class FetchQuiz(TriggeredAction, action_name="quiz_fetch_quiz"):
    """
    Fetches a Quiz
    param 0: Quiz ID
    param 1: Variable to store the fetched Quiz in
    """
    async def run_action(self, message: TGMessage) -> str:
        qid = self.read_param(0)
        out_var = self.read_param(1)
        # get the quiz
        quiz = Quiz.load(qid)
        self.varstore[out_var] = quiz
        return ""



#######################################
#   Operator commands
#######################################
#######################################
#   Sessions
#######################################

class BeginQuizEditSession(TriggeredAction, action_name="quiz_begin_edit"):
    """
    Tries to start an edit session for a quiz, stores results.
    param 0: quiz_id to edit
    param 1: variable to store success/fail
    """
    async def run_action(self, message: TGMessage) -> str:
        quiz_id = self.read_string(0)
        out_var = self.read_string(1)
        uid = UserInfo.User.extract_uid(message)
        EditSession.clear_old_sessions()
        self.varstore[out_var] = EditSession.begin("quiz_edit", uid, quiz_id)
        return ""


class EndQuizEditSession(TriggeredAction, action_name="quiz_finish_edit"):
    """
    Tries to end an editing session for a quiz, stores results.
    param 0: quiz_id to edit
    param 1: variable to store success/fail
    """
    async def run_action(self, message: TGMessage) -> str:
        uid = UserInfo.User.extract_uid(message)
        quiz_id = self.read_string(0)
        out_var = self.read_string(1)
        EditSession.clear_old_sessions()
        self.varstore[out_var] = EditSession.end("quiz_edit", uid, quiz_id)
        return ""


class CheckQuizEditSession(TriggeredAction, action_name="quiz_check_sessions"):
    """
    Checks session state and stores "none" if no ongoing sessions,
    "active" if session matching quiz ID exists,
    "busy" if there are ongoing sessions but noen match this ID.
    param 0: quiz_id to edit
    param 1: variable to store result
    """
    async def run_action(self, message: TGMessage) -> str:
        quiz_id = self.read_string(0)
        out_var = self.read_string(1)
        uid = UserInfo.User.extract_uid(message)
        EditSession.clear_old_sessions()
        sessions = EditSession.find_sessions("quiz_edit", uid)
        result = ""
        if len(sessions) == 0:
            result = "none"
        elif quiz_id in sessions:
            EditSession.refresh("quiz_edit",uid, quiz_id)
            result = "active"
        else:
            result = "busy"
        self.varstore[out_var] = result
        return ""


class FindQuizEditSession(TriggeredAction, action_name="quiz_find_session"):
    """
    Checks session state and stores num
    param 0: variable to store result
    param 1: variable to store quiz id if found
    """
    async def run_action(self, message: TGMessage) -> str:
        out_var = self.read_string(0)
        out_var_quiz = self.read_string(1)
        uid = UserInfo.User.extract_uid(message)
        EditSession.clear_old_sessions()
        # find any sessions by user
        sessions = EditSession.find_sessions("quiz_edit", uid)
        # if exactly one found, return it
        if len(sessions) == 1:
            EditSession.refresh("quiz_edit",uid, sessions[0])
            self.varstore[out_var_quiz] = sessions[0]
        self.varstore[out_var] = len(sessions)
        return ""


#######################################
#   Quiz manipulation
#######################################


class CreateQuiz(TriggeredAction, action_name="quiz_create"):
    """
    param 0: quiz ID
    param 1: variable to store results
    """
    async def run_action(self, message: TGMessage) -> str:
        quiz_id = self.read_string(0)
        uid = message.from_user.id
        quiz = Quiz.create(uid,quiz_id,"(Без названия)",45)
        self.write_param(1, quiz)
        if quiz is not None:
            EditSession.begin("quiz_edit",uid,quiz.id)
        return ""


class RenameQuiz(TriggeredAction, action_name="quiz_rename"):
    """
    Renames a given quiz.
    param 0: quiz_id
    param 1: new name
    """
    async def run_action(self, message: TGMessage) -> str:
        newname = self.read_string(1)
        quiz_id = self.read_string(0)
        # more error checking not needed at this point
        Quiz.load(quiz_id).rename(newname)
        return ""


class SetDefaultQuestionTime(TriggeredAction, action_name="quiz_set_default_time"):
    """

    """

    async def run_action(self, message: TGMessage) -> str:
        pass


##########################################
#   Question editing
##########################################


class AddQuestion(TriggeredAction, action_name="quiz_add_question"):
    """
    param 0: quiz ID to add to
    param 1: variable to store function outcome
    param 2: in, out variable to store question number,
        in: -1 to add the question at the end, else the question is added under that number
        out: -1 if the question was not added, else the number actually assigned to the question
    param 3: true if the question replaces an existing one, false if it is inserted.
    """
    async def run_action(self, message: TGMessage) -> str:
        quiz_id = self.read_string(0)
        replace = self.read_param(3)
        # get desired index - user facing side indexes from 1
        question_index = self.varstore[self.read_string(2)]
        if question_index != -1:
            question_index -= 1
        # pre-load failure
        self.write_param(2, -1)
        result =""
        if message.reply_to_message is None:
            self.write_param(1,"must_reply")
            return ""
        if message.reply_to_message.poll is None:
            self.write_param(1,"no_poll")
            return ""
        poll = message.reply_to_message.poll
        if poll.correct_option_id is None:
            self.write_param(1,"wrong_poll")
            return ""
        quiz = Quiz.load(quiz_id)
        if quiz is None:
            self.write_param(1,"quiz_not_found")
            return ""
        # prepare the question
        q = Question(quiz_id, -1, poll.question, [option.text for option in poll.options], poll.correct_option_id,"")
        # if set to replace try to do it
        if replace:
            if quiz.replace_question(q, question_index):
                self.write_param(2, question_index + 1)
                self.write_param(1,"ok")
                return ""
            # write error on fail
            self.write_param(1, "replace_out_of_range")
            return ""
        # else insert question as needed and get the resulting number
        question_index = quiz.add_question(q, question_index)
        self.write_param(2,question_index + 1)
        self.write_param(1,"ok")
        return ""


class RemoveQuestion(TriggeredAction, action_name="quiz_delete_question"):
    """
    param 0: quiz ID to delete from
    param 1: question index - 1-indexed. pass -1 to delete the last question.
    param 2: out result, of (ok, quiz_not_found, invalid_question)
    """
    async def run_action(self, message: TGMessage) -> str:
        quiz_id = self.read_string(0)
        index = self.read_int(1)
        quiz = Quiz.load(quiz_id)
        if quiz is None:
            self.write_param(2,"quiz_not_found")
            return ""
        if index != -1:
            index -=1
        if -1 > index >= quiz.count:
            self.write_param(2,"invalid_question")
            return ""
        quiz.remove_question(index)
        self.write_param(2,"ok")
        return ""





class SetSpecificQuestionTime(TriggeredAction, action_name="quiz_question_time"):
    """

    """

    async def run_action(self, message: TGMessage) -> str:
        pass


class QuestionAttach(TriggeredAction, action_name="quiz_question_attach"):
    """
    Attaches media to a question.
    param 0: quiz_id
    param 1: question number, or -1 to attach to last question
    param 2: attachment ID
    param 3: out result
    """

    async def run_action(self, message: TGMessage) -> str:
        quiz_id = self.read_string(0)
        question_index = self.read_int(1)
        msgname = self.read_string(2)
        quiz = Quiz.load(quiz_id)
        if quiz is None:
            self.write_param(3,"quiz_not_found")
            return ""
        if question_index == -1:
            question_index = len(quiz.questions)
        question_index -= 1
        if not 0 < question_index < len(quiz.questions):
            self.write_param(3,"question_not_found")
        quiz.questions[question_index].attach_media(msgname)
        self.write_param(3, "ok")
        return ""
