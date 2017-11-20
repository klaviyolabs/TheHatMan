from types import FunctionType

#Each function in the class is a new command

class BotCommand(object):
    DEFAULT_COMMAND_PREFIX = ''

    def __init__(self, prefix=None):
        self.prefix = prefix if prefix is not None else self.DEFAULT_COMMAND_PREFIX
        self.command_mappings = self._command_map()

    def invalid(self, command, channel, user):
        return "You did not provide a valid *{}* command".format(self.prefix)

    def help(self, command, channel, user):
        commands = ['*{}*'.format(name) for name in self.command_mappings.keys()]
        return 'Available *{}* commands are {}'.format(self.prefix, ', '.join(commands))

    def handle(self, command, channel, user):
        parsed_command = command
        if command.startswith(self.prefix):
            parsed_command = command.replace(self.prefix, '').strip()
        
        for name, function in self.command_mappings.items():
            first, _, rest = parsed_command.partition(' ')
            if first == name:
                remainder = parsed_command.replace(name, '').strip()
                return function(self, remainder, channel, user)

        return self.invalid(command, channel, user)
                
    @classmethod
    def _command_map(cls):
        command_mappings = {}
        for name, value in cls.__dict__.items():
            if not name.startswith('_') and isinstance(value, FunctionType):
                command_mappings[name.replace("_", " ")] = value
        
        command_mappings['help'] = cls.help

        return command_mappings
