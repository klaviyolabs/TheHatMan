from slackclient import SlackClient
from bot.settings import SLACK_BOT_TOKEN, TARGET_CHANNEL

slack_client = SlackClient(SLACK_BOT_TOKEN)

if __name__ == "__main__":
    api_call = slack_client.api_call("channels.list")
    if api_call.get('ok'):
        channels = api_call.get('channels')
        for channel in channels:
            if 'name' in channel and channel.get('name') == TARGET_CHANNEL:
                print("Channel ID for '" + channel['name'] + "' is " + channel.get('id'))
    else:
        print("could not find channel with the name " + TARGET_CHANNEL)

