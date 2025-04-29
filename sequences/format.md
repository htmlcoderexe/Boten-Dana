# Sequence file structure

## Overall structure

Each Sequence must have the following attributes:

* ``name``: internal sequence name. Recommended to match the file name, must be unique.
* ``display_name``: Sequence name as displayed in the bot' dashboard.
* ``description``: A short description, shown when viewing a specific sequence.
* ``version``: A list of 4 integers (major, minor, revision, build).
* ``triggers``: Contains *Triggers* defined in this sequence.
* ``subseqs``: Contains *Subsequences*, lists of *Actions* to be taken upon triggering.

Optionally, the following attributes may be present:

* ``stringpools``: Named lists of strings internal to this sequence, to be used by the Actions.
* ``config_vars``: Definitions of persistent variables that may be accessed by the sequence and configured by the operator.
* ``commands``: Contains any commands to be registered.


## Triggers

Each *Trigger* must have the following attributes:

* ``type``: the type of this *Trigger*, which determines how it matches the incoming messages
* ``params``: parameters that affect the behaviour of this *Trigger* and what it matches.
*  ``subseq``: the *Subsequence* name to activate if the *Trigger* matches.

Additionally, the following attributes may also be present:

* ``tag``: if present, the *Trigger* is only evaluated if the message is tagged with a matching *tag* (in the ``message_events`` table).
* ``raw``: if set, the raw string before processing such as removing punctuation is matched against.

## Subsequences

Each *Subsequence* is identified by a name unique to the *Sequence* and contains a list of *Actions* to be executed sequentially.

## Actions

Each *Action* must have the following attributes:

* ``action``: the type of this *Action* which specifies the action to be performed.
* ``params``: a list of parameters to be passed to this *Action*. Parameters can be stored as any JSON datatype, although *Actions* generally expect ``int``, ``string``, or something that can be coerced into those types. String parameter values starting with an asterisk (``*``) are interpreted as variable pointers and are attempted to be resolved when running the *Subsequence*.

Additionally, the following attributes may also be present:

* ``target``: if set, the *Action* will act upon the message the current message is a reply to. If the current message doesn't have a message it is replying to, the *Action* will return a value equal to its type with ``_no_target`` appended. Currently any value Python evaluates to ``True`` has this effect, but for the sake of forward compatibility, using the exact value of ``reply`` is recommended

## List of Trigger types

### String matching triggers

Those return a string if there's a match, otherwise an empty string.
#### ``text_exact``

Matches the exact text.

Parameters:

1. The string to match.
#### ``text_prefix``

Matches any text starting with a prefix.

Parameters:

1. The prefix to match.
2. If True, returns the whole string, else the prefix is removed and the string trimmed.
#### ``text_suffix``

Matches any text ending with a suffix.

Parameters:

1. The suffix to match.
2. If True, returns the whole string, else the suffix is removed and the string trimmed.
#### ``text_contains``

Matches if the text contains the string anywhere.

Parameters:

1. The string to match.

## List of *Actions*

### Flow Control

#### ``if_eq``

Compares two values, then triggers one of two *Subsequences* based on the equality.

Parameters:

1. First value to compare.
2. Second value to compare.
3. The *Subsequence* to trigger if the values are equal.
4. The *Subsequence* to trigger if the values are not equal.

#### ``gosub``

Returns its parameter, therefore triggering the corresponding *Subsequence*.

Parameters:

1. *Subsequence* name to trigger. 

### Variable manipulation

#### ``add``

Adds two values as numbers and writes to a variable.

Parameters:

1. The first value.
2. The second value.
3. The variable to write the result to.
#### ``concat``

Combines two values and writes to a variable.

Parameters:

1. The first value.
2. The second value.
3. The variable to write the result to.

#### ``count``

Counts items in a given variable and stores the value in a variable. For strings, this conveniently returns their length.

Parameters:

1. Variable name to count the items from.
2. Variable name to store the count into.

#### ``fmt_list``

Formats a list using a template, and puts the resulting string into a variable.

Parameters:

1. Variable containing the list.
2. *String Pool* name for the single entry template
3. Variable to receive the formatted output.

#### ``get_match``

Loads the trigger's match data.

Parameters:

1. Name of the variable to receive the data.

#### ``load_env``

Loads an environment variable into var_store.

Parameters:

1. Name of the environment variable.
2. Name of the var_store variable.

#### ``obj_read``

Retrieves a property from an object stored in a variable and stores the result into a nother variable.

Parameters:

1. Variable containing the object.
2. Property name to read.
3. Variable to receive the property value.

#### ``roll_chance``

Rolls a random number from 0 to 1, stores ``true``/``false`` depending on whether the number is below or above the chance parameter.

Parameters:

1. Random chance from ``0.0`` to ``1.0``.
2. Variable to receive the roll's result.

### Output

#### ``emit_text``

Emits a string from an internal *String Pool*, substituting any ``{tags}`` with variables from var_store. On success, the sent message's ID will be stored in ``__last_msg``.

Parameters:

1. *String Pool* name
2. The time to keep the message before deleting, in seconds. -1 keeps the message indefinitely.
3. Optional. A tag to apply to the sent message.

#### ``emit_poll``

Posts a poll (a question with multiple answer choices selectable by users). On success, the sent message's ID will be stored in ``__last_msg``.

Parameters:

1. Text of the question
2. Answer options, as a list of strings.
3. Index of the correct option.
4. Time before the poll expires.
5. Type of the poll between ``quiz`` and ``regular``.
6. Specifies whether the voting should be anonymous. Note that bots do not receive answers from anonymous polls.
7. Variable to store the resulting poll's ID.

### Information actions

#### ``check_message_type``

Checks if a message is from a regular user, a bot or a channel.

Parameters:

1. Variable to store the result in.

Returns: 

``error_no_target`` if set to target the replied message and there isn't one.

#### ``get_uid``

Gets a UserID out of the message. If the message is of a special type like anonymous channel message, a different unique ID is extracted.

Parameters:

1. Variable to store the UserID in.

#### ``get_user``

Retrieves information about someone in a particular chat and stores into var_store.
See **``UserInfo.User``** class to see all the available fields, some commonly used ones are listed below:

* ``current_nick`` - user's current nickname.
* ``nicknames`` - user's remaining nicknames, if any.
* ``id`` - user's numerical ID.
* ``current_chat`` - user's information relevant to this chat - see **``UserInfo.ChatUserInfo``** for more information.

Parameters:

1. Prefix for the variable to store the information.

### Message manipulation

#### ``keep_msg``

Cancels a scheduled message removal.

Parameters:

None. For technical reasons, a single empty parameter should be included for now.

#### ``kill_msg``

Removes a message.

Parameters:

1. The delay before removing the message.

#### ``tag_msg``

Associates a tag and optional extra data with a message.

Parameters:

1. The tag to apply.
2. Message ID to use - special value ``-1`` resolves to ``__last_msg`` and ``0`` to context message.
3. through 9. - optional data to add. Must be serialisable to ``int`` or ``string``.

### Score actions

#### ``score_get``

Retrieves a specific score for a single user.

Parameters:

1. User ID.
2. Name of the score.
3. Variable to store the score.
4. Scope out of ``all``, ``day``, ``week``, ``month``, ``year``. Defaults to ``all``.

#### ``score_up``

Modifies a specific score for the single user.

Parameters:

1. User ID.
2. Name of the score.
3. The amount to modify the score by. 
4. Variable to score the updated score.

#### ``scoreboard``

Fetches a scoreboard and stores it into var_store.

Parameters:

1. Name of the score to retrieve.
2. Amount of users to display.
3. The variable name to store the user table in (``list`` of ``tuple`` of ``string, int``)

### QDB functions

#### ``qdb_get_user``

Gets quotes saved for a particular user.

Parameters:

1. UID of the user
2. Variable name to hold the list.
3. Amount of quotes to get, -1 to get all eligible quotes.
4. "local" to get quotes only for the current chat, "global" to get all.
5. Minimum score of the quotes to be retrieved.
6. Sorting mode: "score", "newest", "random", "oldest" (default)

#### ``qdb_save``

Saves a quote, stores the ID and the result in variables. Possible results are:

* ``ok`` - the quote was saved and the ID of the new quote is stored.
* ``exists`` - the message was already saved. The ID of the existing quote is stored.
* ``no_text`` - the message doesn't contain any text. 0 is stored in the ID variable.

Parameters:

1. Variable to save the stored quote ID in.
2. Variable to save the result of the action

#### ``qdb_upvote``

Modifies a quote's rating. If the quote does not exist, the new score is set to -1.

Parameters:

1. Quote ID.
2. Amount to add to the rating.
3. Variable to store the new score in.

### *Message Store*

#### ``emit_saved_message``

Emits a saved message the *Message Store*. On success, the sent message's ID will be stored in ``__last_msg``.

Parameters:

1. Message name.
2. The time to keep the message before deleting, in seconds. -1 keeps the message indefinitely.
3. Optional. A tag to apply to the sent message.

#### ``fetch_from_pool``

Retrieves a random saved message ID from a pool.

Parameters:

1. *Message Pool* name.
2. Variable to store the returned ID.
#### ``save_msg``

Saves a message into the *Message Store* system.

Parameters:

1. Mode to set message name: ``var_store`` use a specific variable ``param`` use the match from the trigger ``prefixed`` use a prefixed name
2. Specific to the mode: variable name or prefix, unused if mode is ``param``
3. Variable to store the resulting message name to

### Userlists

#### ``userlist_check``, ``userlist_add``, ``userlist_remove``

All 3 act on a user is on a given *User List* (``user_lists`` table) and take the same parameters.

The functions respectively check user's presence on a list, add the user to a list and remove the user from a list. The two functions modifying the lists return ``True`` only if a change happened.

Parameters:

1. User ID to act on.
2. *Userlist* to manipulate.
3. Variable to store the result in.
