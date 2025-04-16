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

## Triggers

Each *Trigger* must have the following attributes:

* ``type``: the type of this *Trigger*, which determines how it matches the incoming messages
* ``params``: parameters that affect the behaviour of this *Trigger* and what it matches.
*  ``subseq``: the *Subsequence* name to activate if the *Trigger* matches.

Additionally, the following attributes may also be present:

* ``tag``: if present, the *Trigger* is only evaluated if the message is tagged with a matching *tag* (in the ``message_tags`` table).

## Subsequences

Each *Subsequence* is identified by a name unique to the *Sequence* and contains a list of *Actions* to be executed sequentially.

## Actions

Each *Action* must have the following attributes:

* ``action``: the type of this *Action* which specifies the action to be performed.
* ``params``: a list of parameters to be passed to this *Action*.

Additionally, the following attributes may also be present:

* ``target``: if set, the *Action* will act upon the message the current message is a reply to. If the current message doesn't have a message it is replying to, the *Action* will return a value equal to its type with ``_no_target`` appended. Currently any value Python evaluates to ``True`` has this effect, but for the sake of forward compatibility, using the exact value of ``reply`` is recommended.

## List of Trigger types

### String matching triggers

Those return a string if there's a match, otherwise an empty string.

### ``text_exact``

Matches the exact text.

Parameters:

1. The string to match.

### ``text_prefix``

Matches any text starting with a prefix.

Parameters:

1. The prefix to match.
2. If True, returns the whole string, else the prefix is removed and the string trimmed.

### ``text_suffix``

Matches any text ending with a suffix.

Parameters:

1. The suffix to match.
2. If True, returns the whole string, else the suffix is removed and the string trimmed.

### ``text_contains``

Matches if the text contains the string anywhere.

Parameters:

1. The string to match.

## List of *Actions*

### Responses

### ``reply_text``

Responds to the message using a string from an internal *String Pool*, substituting any ``{tags}`` with variables from var_store.

Parameters:

1. *String Pool* name
2. The time to keep the message before deleting, in seconds. -1 keeps the message indefinitely.
3. A tag to apply to the sent message.


### ``reply_text_table``

Responds to the message using a string from an internal *String Pool*, and formatting a table list using an additional template.

Parameters:

1. *String Pool* name for the message template
2. *String Pool* name for the single entry template
3. Variable to contain a table  (``list`` of ``tuple`` of ``string, int``)
4. The time to keep the message before deleting, in seconds. -1 keeps the message indefinitely.
5. A tag to apply to the sent message.

### ``reply_pool``

Responds to the message using a saved message from a message pool.

Parameters:

1. *Message Pool* name.
2. The time to keep the message before deleting, in seconds. -1 keeps the message indefinitely.
3. A tag to apply to the sent message.

### ``check_message_type``

Checks if a message is from a regular user, a bot or a channel.

Parameters:

1. Variable to store the result in.

Returns:

``check_message_type_no_target`` if set to target the replied message and there isn't one.

### ``scoreboard``

Fetches a scoreboard and stores it into var_store.

Parameters:

1. Name of the score to retrieve.
2. Amount of users to display.
3. The variable name to store the user table in (``list`` of ``tuple`` of ``string, int``)

### ``score_get``

Retrieves a specific score for a single user.

Parameters:

1. Name of the score.
2. Variable to store the score.

### ``score_up``

Modifies a specific score for the single user.

Parameters:

1. Name of the score.
2. The amount, as a ``string``. If prefixed with ``*``, the amount is taken from that variable instead.
3. Variable to score the updated score.

### ``whois``

Retrieves information about someone in a particular chat and stores into var_store.
Following variables will be filled (ignoring the prefix):

* ``usernick`` - user's current nickname.
* ``usernicks`` - user's remaining nicknames, if any.
* ``userid`` - user's numerical ID.
* ``userrep`` - user's reputation.
* ``usermedals`` - user's quiz medals, if any.
* ``recent`` - time since last action.
* ``returner`` - filled if the user joined multiple times.
* ``quotes`` - 3 random quotes from the user.

Parameters:

1. Prefix for the variables to be filled with the information.

### ``qdb_get_user``

Gets quotes saved for a particular user.

Parameters:

1. Amount of quotes to get, -1 to get all eligible quotes.
2. "local" to get quotes only for the current chat, "global" to get all.
3. Minimum score of the quotes to be retrieved.
4. Sorting mode: "score", "newest", "oldest" (default)
5. Variable name to hold the list.

### Message manipulation

### ``kill_msg``

Removes a message.

Parameters:

1. The delay before removing the message.

### ``save_msg``

Saves a message into the *Message Store* system.

Parameters:

1. Mode to set message name: ``var_store`` use a specific variable ``param`` use the match from the trigger ``prefixed`` use a prefixed name
2. Specific to the mode: variable name or prefix, unused if mode is ``param``
3. Variable to store the resulting message name to

### Flow Control

### ``roll_random``

Rolls a random number from 0 to 1, fails if above threshold, succeeds if below.

Parameters:

1. Variable to load the random chance from.
2. Return this if success.
3. Return this if failure.

### ``check_userlist``

Check if a user is on a given *User List* (``user_lists`` table)

Parameters:

1. *User List* to check.
2. Return this if user is on the list.
3. Return this if user is not on the list.

### ``load_env``

Loads an environment variable into var_store.

Parameters:

1. Name of the environment variable.
2. Name of the var_store variable.

### ``gosub``

Returns its parameter, therefore triggering the corresponding *Subsequence*, given no later *Actions* return a value.

Parameters:

1. *Subsequence* name to trigger. If it starts with an ``*``, the value is taken from the variable with this name.
