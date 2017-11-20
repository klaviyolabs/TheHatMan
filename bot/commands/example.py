from bot import settings
from bot.commands.base import BotCommand

class ExampleCommand(BotCommand):
    DEFAULT_COMMAND_PREFIX = 'example'

    def hello(self, command, channel, user):
        return "Hello, World"