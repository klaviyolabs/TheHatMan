from peewee import SqliteDatabase

# Fill these in
SLACK_BOT_TOKEN=''
BOT_ID=''
BOT_NAME=''
DB_FILE=''
TARGET_CHANNEL=''
CHANNEL_ID=''

# Don't change stuff down here
database = SqliteDatabase(DB_FILE)

