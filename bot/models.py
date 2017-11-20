from peewee import *
from bot import settings

db = settings.database

class HatLog(Model):
    user_id = CharField(null = False)
    start_time = DateTimeField(null = False)
    end_time = DateTimeField(null = True)

    class Meta:
        database = db

class HatQueue(Model):
    user_id = CharField(null = False)
    start_time = DateTimeField(null = False)
    end_time = DateTimeField(null = True)

    class Meta:
        database = db

class HatPool(Model):
    owner_user_id = CharField(null = False)
    user_id = CharField(null = False)
    end_time = DateTimeField(null = True)

    class Meta:
        database = db

class SlackUserInfo(Model):
    user_id = CharField(null = False)
    name = CharField(null = False)
    tip = IntegerField(default = 0)

