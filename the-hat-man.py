import settings
import time
import sqlite3
import pytz
from datetime import datetime
from dateutil.parser import parse
from slackclient import SlackClient

BOT_ID = settings.BOT_ID

# constants
AT_BOT = "<@" + BOT_ID + ">"
EXAMPLE_COMMAND = "hat"

# instantiate Slack & clients
slack_client = SlackClient(settings.SLACK_BOT_TOKEN)

def handle_command(command, channel, user):
    """
        Receives commands directed at the bot and determines if they
        are valid commands. If so, then acts on the commands. If not,
        returns back what it needs for clarification.
    """
    response = "Not sure what you mean. Use the *" + EXAMPLE_COMMAND + \
               "* command"
    if command.startswith(EXAMPLE_COMMAND):
        if command == 'hat on':
            response = command_hat_on(channel, user)
        elif command == 'hat off':
            response = command_hat_off(channel, user)
        else:
            response = "You did not provide a valid *hat* command"
    slack_client.api_call("chat.postMessage", channel=channel,
                          text=response, as_user=True)

def get_user_name(user_id):
    conn = sqlite3.connect('hat-man.db')
    c = conn.cursor()
    c.execute('SELECT name FROM user_info WHERE user_id = ?', [user_id])
    result = c.fetchone()
    if not result:
        api_results = slack_client.api_call("users.info", user=user_id)
        name = api_results['user']['profile']['display_name']
        c.execute('INSERT INTO user_info VALUES (?,?)', (user_id, name))
        return name
    else:
        return result[0]


def command_hat_off(channel, user):
    # Make sure the user using the command has the hat
    response = None
    conn = sqlite3.connect('hat-man.db')
    c = conn.cursor()
    c.execute('SELECT * FROM hat_log WHERE end is null')
    # If we don't get a row back, it means no one has the hat
    result = c.fetchone()
    now = datetime.now(tz=pytz.utc)
    if not result:
        response = 'No one has the hat now!'
    else:
        if result[0] != user:
            response = 'You do not have the hat. <@{}> has the hat. They\'ve had it since {}'.format(result[0], result[1])
        else:
            timedelta = now - parse(result[1])
            params = (now, result[0], result[1])
            c.execute('UPDATE hat_log SET end = ? WHERE user = ? AND start = ?', params)
            conn.commit()
            response = 'You have given up the hat. You had it for {}'.format(timedelta)
    conn.close()
    return response


def command_hat_on(channel, user):
    response = None
    conn = sqlite3.connect('hat-man.db')
    c = conn.cursor()
    c.execute('SELECT * FROM hat_log WHERE end is null')
    # If we don't get a row back, it means we can get the hat
    result = c.fetchone()
    now = datetime.now(tz=pytz.utc)
    if not result:
        params = (user, now, None)
        c.execute('INSERT INTO hat_log VALUES (?,?,?)', params)
        conn.commit()
        response = 'You have the hat now!'
    else:
        if user == result[0]:
            response = 'You already have the hat!'
        else:
            response = 'You can\'t take the hat. <@{}> has the hat. They\'ve had it since {}'.format(result[0], result[1])
    conn.close()
    return response



def parse_slack_output(slack_rtm_output):
    """
        The Slack Real Time Messaging API is an events firehose.
        this parsing function returns None unless a message is
        directed at the Bot, based on its ID.
    """
    output_list = slack_rtm_output
    if output_list and len(output_list) > 0:
        for output in output_list:
            if output and 'text' in output and AT_BOT in output['text']:
                # return text after the @ mention, whitespace removed
                return output['text'].split(AT_BOT)[1].strip().lower(), \
                       output['channel'], output['user']
    return None, None, None


if __name__ == "__main__":
    conn = sqlite3.connect('hat-man.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS hat_log
             (user text not null, start text not null, end text)''')
    c.execute('''CREATE TABLE IF NOT EXISTS user_info
             (user_id text not null, name text not null)''')
    conn.commit()
    conn.close()

    READ_WEBSOCKET_DELAY = 1 # 1 second delay between reading from firehose
    if slack_client.rtm_connect():
        print("the-hat-man connected and running!")
        while True:
            command, channel, user = parse_slack_output(slack_client.rtm_read())
            if all([command, channel, user]):
                handle_command(command, channel, user)
            time.sleep(READ_WEBSOCKET_DELAY)
    else:
        print("Connection failed. Invalid Slack token or bot ID?")
