
from dotenv import load_dotenv
import os


from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from slack_sdk import WebClient
load_dotenv()




APP_TOKEN = os.getenv("APP_TOKEN")
BOT_TOKEN = os.getenv("BOT_TOKEN")


app = App(token=BOT_TOKEN)
client = WebClient(token=BOT_TOKEN)


def get_user_fav_artist(user_id):
    try:
        user_info = app.client.users_info(user=user_id)
        artist = user_info['user']
        print(artist)
    except Exception as e:
        print(f"Error fetching user info for {user_id}: {e}")
        return None

get_user_fav_artist("U086TNY7PE0")


if __name__ == "__main__":
    socketmodehandler =SocketModeHandler(app, APP_TOKEN)
    socketmodehandler.start()