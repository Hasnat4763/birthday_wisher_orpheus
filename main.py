import dotenv
import os
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from slack_sdk import WebClient
dotenv.load_dotenv()

APP_TOKEN = os.getenv("APP_TOKEN")
BOT_TOKEN = os.getenv("BOT_TOKEN")

app = App(token=BOT_TOKEN)
client = WebClient(token=BOT_TOKEN)

@app.command("/birthday_register")
def handle_birthday_register(ack, body):
    user_id = body["user_id"]
    text = body["text"]
    DD,MM = map(int, text.split("/"))
    if (DD > 31 or DD < 1) or (MM > 12 or MM < 1):
        
        ack("Invalid Date or Month Check Again.")
        return
    else:
        if MM == 2 and DD > 29:
            ack ("Invalid Date February only has 29 days")
            return
        ack("Received")
    print(str(DD)+"\n"+str(MM)+"\n"+user_id)

if __name__ == "__main__":
    socketmodehandler =SocketModeHandler(app, APP_TOKEN)
    socketmodehandler.start()