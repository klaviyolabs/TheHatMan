# -*- coding: utf-8 -*-

import pytz
import re
from datetime import datetime
from dateutil.parser import parse
import random

from peewee import *

from bot import settings
from bot.commands.base import BotCommand
from bot.models import HatLog, HatQueue, HatPool, SlackUserInfo

# Each function in the class is a new command

class HatCommand(BotCommand):
    DEFAULT_COMMAND_PREFIX = 'hat'

    def __init__(self, slack_client, prefix=None):
        self.slack_client = slack_client
        super(HatCommand, self).__init__(prefix=prefix)

    # Helpers need to be defined as "private" using "_"
    def _get_user_info(self, user_id):
        try:
            return SlackUserInfo.select().where(SlackUserInfo.user_id == user_id).get()
        except DoesNotExist:
            return None

    def _get_user_name(self, user_id):
        user_info = self._get_user_info(user_id)
        if user_info:
            return user_info.name, None
        else:
            api_results = self.slack_client.api_call(
                "users.info", user=user_id.upper())
            name = api_results['user']['profile']['display_name']
            entry = SlackUserInfo.create(user_id=user_id, name=name)
            return name, entry

    def _get_current_hat_owner(self):
        try:
            entry = HatLog.select().where(HatLog.end_time.is_null(True)
                                          ).order_by(HatLog.start_time).get()
            return entry
        except DoesNotExist:
            return None

    def _get_pooled_users(self, current_owner_id):
        return HatPool.select().where(HatPool.end_time.is_null(True),
                                      HatPool.owner_user_id == current_owner_id)

    def _get_pooled_user_query(self, user_id):
        return HatPool.select().where(HatPool.end_time.is_null(True),
                                      HatPool.user_id == user_id)

    def _get_pooled_user(self, user_id):
        try:
            return self._get_pooled_user_query(user_id).get()
        except DoesNotExist:
            return None

    def _check_if_already_pooled(self, user_id):
        return self._get_pooled_user_query(user_id).exists()

    def _remove_user_from_queue(self, user, end_time=None):
        if end_time is None:
            end_time = datetime.now(tz=pytz.utc)
        try:
            entry = HatQueue.select().where(HatQueue.end_time.is_null(True),
                                            HatQueue.user_id == user).get()
            entry.end_time = end_time
            entry.save()
            return entry
        except DoesNotExist:
            return None

    def _get_user_in_queue(self, user):
        try:
            entry = HatQueue.select().where(HatQueue.end_time.is_null(True),
                                            HatQueue.user_id == user).get()
            position = HatQueue.select().where(HatQueue.end_time.is_null(
                True), HatQueue.start_time <= entry.start_time).count()
            return entry, position
        except DoesNotExist:
            return None, None

    def _add_user_to_queue(self, user):
        """
           Adds specified user to queue and returns the number of entries in front of them
        """
        now = datetime.now(tz=pytz.utc)
        HatQueue.create(user_id=user, start_time=now)
        return HatQueue.select().where(HatQueue.end_time.is_null(True), HatQueue.start_time < now).count()

    def _get_active_queue_entries(self):
        return HatQueue.select().where(HatQueue.end_time.is_null(True)).order_by(HatQueue.start_time)

    def _get_next_user_in_queue(self):
        try:
            entry = HatQueue.select().where(HatQueue.end_time.is_null(True)
                                            ).order_by(HatQueue.start_time).get()
            return entry
        except DoesNotExist:
            return None

    def _clear_hat_pool(self, owner_id):
        end_time = datetime.now(tz=pytz.utc)
        query = HatPool.update(end_time=end_time).where(HatPool.end_time.is_null(True),
                            HatPool.owner_user_id == owner_id)
        query.execute()

    def _change_hat_pool_owner(self, current_owner_id, new_owner_id):
        query = HatPool.update(owner_user_id=new_owner_id).where(HatPool.end_time.is_null(True),
                        HatPool.owner_user_id == current_owner_id)
        query.execute()


    def _give_up_hat(self, hat_log_entry, end_time=None):
        if end_time is None:
            end_time = datetime.now(tz=pytz.utc)

        hat_log_entry.end_time = end_time
        hat_log_entry.save()

        return hat_log_entry

    def _daily_deploy_count(self):
        today = datetime.now(tz=pytz.timezone('US/Eastern')
                             ).replace(hour=0, minute=0, second=0)
        return HatQueue.select().where(HatQueue.start_time > today).count()

    def _user_deploy_count(self, user_id):
        return HatQueue.select().where(HatQueue.user_id == user_id).count()

    def _user_pool_count(self, user_id):
        return HatPool.select().where(HatPool.user_id == user_id).count()

    def _check_channel(self, channel):
        if channel != settings.CHANNEL_ID:
            return False
        else:
            return True
    #
    # BEGIN REAL COMMANDS (Not helpers)
    #

    def on(self, command, channel, user):
        if not self._check_channel(channel):
            return 'You cannot use that command in this channel.'
        owner_entry = self._get_current_hat_owner()
        if owner_entry:
            if user == owner_entry.user_id:
                return 'You already have the hat.'
            else:
                return ('You can\'t take the hat. <@{}> has the hat. They\'ve had it since {}. '
                        'Use *hat queue* to join the queue, or *hat pool* to join the pool (with permission).').format(
                    owner_entry.user_id, owner_entry.start_time)
        else:
            # Grab the hat
            now = datetime.now(tz=pytz.utc)
            HatLog.create(user_id=user, start_time=datetime.now(tz=pytz.utc))
            queue_entry = self._remove_user_from_queue(user, end_time=now)
            if queue_entry:
                return 'You have the hat now! You waited for {} in the queue.'.format(now - parse(queue_entry.start_time))
            else:
                return 'You have the hat now!'

    def off(self, command, channel, user):
        if not self._check_channel(channel):
            return 'You cannot use that command in this channel.'
        owner_entry = self._get_current_hat_owner()
        if owner_entry:
            if user == owner_entry.user_id:
                now = datetime.now(tz=pytz.utc)
                owner_entry = self._give_up_hat(owner_entry, end_time=now)
                timedelta = now - parse(owner_entry.start_time)
                pooled_users = self._get_pooled_users(owner_entry.user_id)
                if pooled_users.count() == 0:
                    queued_user = self._get_next_user_in_queue()
                    if queued_user:
                        return 'You have given up the hat. You had it for {}. <@{}> is next in the queue'.format(timedelta, queued_user.user_id)
                    else:
                        return 'You have given up the hat. You had it for {}.'.format(timedelta)
                else:
                    first_pooled = pooled_users[0]
                    new_owner_id = first_pooled.user_id
                    first_pooled.end_time = now
                    first_pooled.save()
                    HatLog.create(user_id=new_owner_id, start_time=datetime.now(tz=pytz.utc))
                    self._remove_user_from_queue(new_owner_id)
                    self._change_hat_pool_owner(
                        owner_entry.user_id, new_owner_id
                    )
                    return 'You have given up the hat. You had it for {}. <@{}> now has the hat.'.format(timedelta, new_owner_id)
            else:
                return 'You do not have the hat. <@{}> has the hat. They\'ve had it since {}'.format(
                    owner_entry.user_id, owner_entry.start_time)
        else:
            return 'No one has the hat now.'

    def who(self, command, channel, user):
        owner_entry = self._get_current_hat_owner()
        if not owner_entry:
            return 'No one has the hat now.'
        else:
            pooled_users = self._get_pooled_users(owner_entry.user_id)
            if pooled_users.count() == 0:
                return '<@{}> has the hat. They\'ve had it since {}'.format(owner_entry.user_id, owner_entry.start_time)
            else:
                pooled_ids = ['<@{}>'.format(user.user_id)
                              for user in pooled_users]
                verb = 'is'
                if len(pooled_ids) > 1:
                    verb = 'are'
                return '<@{}> has the hat. They\'ve had it since {}. {} {} also in the hat pool.'.format(
                    owner_entry.user_id, owner_entry.start_time, ', '.join(pooled_ids), verb)

    def queue(self, command, channel, user):
        if not self._check_channel(channel):
            return 'You cannot use that command in this channel.'
        queued_user, position = self._get_user_in_queue(user)
        owner_entry = self._get_current_hat_owner()
        if owner_entry and owner_entry.user_id == user:
            return 'You can\'t join the queue, you already have the hat.'
        if queued_user:
            timedelta = datetime.now(tz=pytz.utc) - \
                parse(queued_user.start_time)
            return 'You are already in the queue. Your position is {}. You have been waiting for {}.'.format(position, timedelta)
        else:
            position = self._add_user_to_queue(user)
            return 'You have joined the queue. There are {} people in front of you'.format(position)

    def dequeue(self, command, channel, user):
        if not self._check_channel(channel):
            return 'You cannot use that command in this channel.'
        queued_user, position = self._get_user_in_queue(user)
        if not queued_user:
            return 'You are not in the queue.'
        else:
            entry = self._remove_user_from_queue(user)
            timedelta = entry.end_time - parse(entry.start_time)
            return 'You have left the queue. You waited for {}'.format(timedelta)

    def queued(self, command, channel, user):
        queue_entries = self._get_active_queue_entries()
        if queue_entries.count() == 0:
            return 'No one is in the queue.'
        else:
            response = ''
            counter = 1
            for entry in queue_entries:
                name, _ = self._get_user_name(entry.user_id.upper())
                response += '*{}*. {}\n'.format(counter, name)
                counter += 1
            return response

    def force(self, command, channel, user):
        if not self._check_channel(channel):
            return 'You cannot use that command in this channel.'
        if command == "off":
            owner_entry = self._get_current_hat_owner()
            if owner_entry:
                now = datetime.now(tz=pytz.utc)
                owner_entry = self._give_up_hat(owner_entry, end_time=now)
                self._clear_hat_pool(owner_entry.user_id)
                timedelta = now - parse(owner_entry.start_time)
                queued_user = self._get_next_user_in_queue()
                if queued_user:
                    return 'The hat has been forced off of <@{}>. They had it for {}. <@{}> is next in the queue'.format(
                        owner_entry.user_id, timedelta, queued_user.user_id)
                else:
                    return 'The hat has been forced off of <@{}>. They had it for {}.'.format(owner_entry.user_id, timedelta)
            else:
                return 'No one has the hat now.'
        else:
            return 'Valid *hat force* commands are: *off*'

    def pool(self, command, channel, user):
        if not self._check_channel(channel):
            return 'You cannot use that command in this channel.'
        owner_entry = self._get_current_hat_owner()
        if not owner_entry:
            return 'No one has the hat, so you can\'t pool.'
        else:
            if owner_entry.user_id == user:
                return 'You can\'t *hat pool* with yourself.'

            if self._check_if_already_pooled(user):
                return 'You are already in the pool.'
            # Create pool record
            HatPool.create(owner_user_id=owner_entry.user_id, user_id=user)
            queued_user, position = self._get_user_in_queue(user)
            if queued_user:
                entry = self._remove_user_from_queue(user)
                timedelta = entry.end_time - parse(entry.start_time)
                return '<@{}> is now pooling with <@{}>. You waited in the queue for {}'.format(user, owner_entry.user_id, timedelta)
            else:
                return '<@{}> is now pooling with <@{}>'.format(user, owner_entry.user_id)
    
    def unpool(self, command, channel, user):
        if not self._check_channel(channel):
            return 'You cannot use that command in this channel.'
        owner_entry = self._get_current_hat_owner()
        if not owner_entry:
            return 'No one has the hat, so you can\'t unpool.'
        else:
            pooled_user = self._get_pooled_user(user)
            if pooled_user:
                pooled_user.end_time = datetime.now(tz=pytz.utc)
                pooled_user.save()
                return '<@{}> is no longer pooling'.format(user)
            else:
                return '<@{}> is not in the pool'.format(user)

    def stats(self, command, channel, user):
        count = self._daily_deploy_count()
        return 'There have been {} deploys today.'.format(count)

    def info(self, command, channel, user):
        user_info = self._get_user_info(user)
        if not user_info:
            name, user_info = self._get_user_name(user)

        deploy_count = self._user_deploy_count(user)
        pool_count = self._user_pool_count(user)

        return 'You have deployed {} times, and been in {} deploy pools. You have been tipped {} times'.format(
            deploy_count, pool_count, user_info.tip)

    def tip(self, command, channel, user):
        # Get user to tip from command
        match = re.search('<@(.+?)>', command)
        if not match:
            return 'You must provide a user to tip for *hat tip*'

        tipped_user_id = match.group(1).upper()

        if tipped_user_id == user and user != 'U41TGMU3G':
            return 'You can\'t tip yourself. Cheater.'

        user_info = self._get_user_info(tipped_user_id)
        if not user_info:
            name, user_info = self._get_user_name(tipped_user_id)
        user_info.tip = user_info.tip + 1
        user_info.save()
        if user == 'U41TGMU3G' and tipped_user_id == user:
            return 'You can\'t tip yourself. Cheater.'
        else:
            return '<@{}> has tipped <@{}>!'.format(user, tipped_user_id)

    def bless(self, command, channel, user):
        return '{}{}'.format(self.tip(command, channel, user), ' :pray: ')

    def memeify(self, command, channel, user):
        memified = []
        lower = command.lower()
        for index, letter in enumerate(lower):
            if index % 2 == 1:
                memified.append(letter.upper())
            else:
                memified.append(letter)

        return ''.join(memified)

    def facts(self, command, channel, user):
        factoids = [u'The beret started out as a Pyrenean shepherd’s hat.',
                    u'The tall chef’s hat or toque blanche traditionally had 100 pleats to represent the number of ways an egg could be cooked.',
                    u'Students of the medieval theologian John Duns Scotus (1265-1308) were the first to wear dunce’s caps.',
                    u'The earliest record of hat-wearing comes from a cave at Lussac-les-Châteaux in central France.',
                    u'In 1922, police reserves were called into handle a "straw hat riot" in New York in which scores of straw hats were destroyed by marauding "rowdies". To prevent these attacks some people destroyed their own hats first.',
                    u'The classic "Brooklyn cap" with its large brim or "bill" was first worn in 1860 by the Brooklyn Excelsiors, an amateur team, and others followed suit.',
                    u'The bowler hat, symbol of the City of London commuter, began life as a riding helmet.',
                    u'The term "Mad as a Hatter" came about as Hat Makers used to use Mercury which is toxic and prolonged useage can cause nerve damage driving hat makers to madness.',
                    u'People have been wearing hats since pre 15,000 BC (the earliest sighting of a painting in a cave in France).',
                    u'Fedora Hats were originally designed for women, then men, and are now worn by both.',
                    u'The Top Hat was first made in London in 1793 by George Dunnage.',
                    u'Baseball Umpires used to wear Top Hats in the 1850’s.',
                    u'Panama Hats are made in Equador not Panama. They were worn by workers building the Panama Canal to prevent sunburn. They are handwoven from a plant called Toquilla.',
                    u'The first person to pull a rabbit out of a Top Hat was a French Man called Louis Compe in 1814.',
                    u'20% of your body heat is lost from your head which is why babies are encouraged to wear them outdoors on cold days.',
                    u'London Taxis have lots of head room as they were designed to incorporate people wearing Top Hats.',
                    u'https://media.giphy.com/media/yCAoGdVUCW5LW/giphy.gif'
                    ]
        return random.choice(factoids)

    def gif(self, command, channel, user):
        images = [u'https://media.giphy.com/media/l1J9sBOqBIvnafnUc/giphy.gif',
                  u'https://media.giphy.com/media/l2YOhDAMRlgnSQkX6/giphy.gif',
                  u'https://media.giphy.com/media/ms5kJmqRGHgLS/giphy.gif',
                  u'https://media.giphy.com/media/QDRJ6IJzFSR1K/giphy.gif',
                  ]
        return random.choice(images)

    def help(self, command, channel, user):
        commands = ['*{}*'.format(name)
                    for name in self.command_mappings.keys()]
        # Hide some commands
        commands.remove('*memeify*')
        commands.remove('*facts*')
        commands.remove('*gif*')

        return 'Available *{}* commands are {}'.format(self.prefix, ', '.join(commands))
