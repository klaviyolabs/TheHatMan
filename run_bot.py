import time
import sys

from collections import OrderedDict
from slackclient import SlackClient

from bot import settings
from bot.models import HatLog, HatQueue, HatPool, SlackUserInfo
from bot.commands.hat import HatCommand
from bot.commands.example import ExampleCommand


this = sys.modules[__name__]

BOT_ID = settings.BOT_ID
db = settings.database

# constants
AT_BOT = "<@" + BOT_ID + ">"
HELP_COMMAND = "help"

# instantiate Slack & clients
slack_client = SlackClient(settings.SLACK_BOT_TOKEN)

# Dictionaries for command lookups
this.prefix_dict = None

def load_commands():
    # Eventually this could potentially use metaprogramming magic to do this for all of the
    # classes in bot.commands, but for now, we'll do it this way
    hat_command = HatCommand(slack_client)
    example_command = ExampleCommand()
    this.prefix_dict = {
        'hat': hat_command,
        'example' : example_command,
        '': hat_command
    }
    this.prefixes = ['hat', 'example', '']

def handle_command(command, channel, user):
    """
        Receives commands directed at the bot and determines if they
        are valid commands. If so, then calls the correct thing for the command. If not,
        returns back what it needs for clarification.
    """
    response = None
    found_prefix = False
    for prefix in this.prefixes:
        if command.startswith(prefix):
            command_instance = this.prefix_dict[prefix]
            response = command_instance.handle(command, channel, user)
            break

    if response is None:
        response = "Not sure what you mean. Use the *{}* command".format(HELP_COMMAND)

    slack_client.api_call("chat.postMessage", channel=channel,
                          text=response, as_user=True)


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

def initialize():
    models = [HatLog, HatQueue, HatPool, SlackUserInfo]
    db.connect()
    for model in models:
        if not model.table_exists():
            model.create_table(True)
    db.close()
    load_commands()

if __name__ == "__main__":
    initialize()

    READ_WEBSOCKET_DELAY = 1  # 1 second delay between reading from firehose
    if slack_client.rtm_connect():
        print("{} connected and running!".format(settings.BOT_NAME))
        while True:
            command, channel, user = parse_slack_output(
                slack_client.rtm_read())
            if all([command, channel, user]):
                handle_command(command, channel, user)
            time.sleep(READ_WEBSOCKET_DELAY)
    else:
        print("Connection failed. Invalid Slack token or bot ID?")
