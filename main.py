import dotenv
import os
import time
import schedule
import threading
from datetime import datetime, timedelta
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from slack_sdk import WebClient
import pytz
from database import init, connect_db
dotenv.load_dotenv()

APP_TOKEN = os.getenv("APP_TOKEN")
BOT_TOKEN = os.getenv("BOT_TOKEN")

app = App(token=BOT_TOKEN)
client = WebClient(token=BOT_TOKEN)

init()



@app.command("/birthday_test")
def handle_birthday_test(ack):
    ack()
    now = datetime.now()
    day, month = now.day, now.month
    
    db = connect_db()
    cursor = db.cursor()
    
    cursor.execute(
        '''
        SELECT user_id FROM birthday_info WHERE day = ? AND month = ?
        ''', (day, month)
    )
    results = cursor.fetchall()
    db.close()
    
    for (user_id,) in results:
        try:
            app.client.chat_postMessage(
                channel=user_id,
                text="Happy Birthday!"
            )
            
        except Exception as e:
            print(f"Error sending birthday wish to {user_id}: {e}")
    



@app.command("/birthday_register")
def handle_birthday_register(ack, body, respond):
    ack()
    user_id = body["user_id"]
    text = body["text"]
    DD,MM = map(int, text.split("/"))
    if (DD > 31 or DD < 1) or (MM > 12 or MM < 1):
        respond("Invalid Date or Month Check Again.")
        return
    else:
        if MM == 2 and DD > 29:
            respond("Invalid Date February only has 29 days")
            return
        elif MM in [4, 6, 9, 11] and DD > 30:
            respond("Invalid Date this month has 30 days only")
            return
    
    userinfo = client.users_info(user=user_id)
    
    if userinfo["ok"]:
        user_tz = userinfo["user"]["tz"]
        print(user_tz)
        
    else:
        respond("Could not fetch user info. Please try again later.")
        return
        
    
    
    try:
        db = connect_db()
        cursor = db.cursor()
        cursor.execute(
            """
            INSERT INTO birthday_info (user_id, day, month, tz)
            VALUES (?,?,?,?)
            
            """, (user_id, DD, MM, user_tz)
            )
        db.commit()
        db.close()
        respond("Your Birthday has been Registered Successfully!")
    except Exception:
        respond("There is a problem contact someone")
    print(str(DD)+"\n"+str(MM)+"\n"+user_id)
    

@app.command("/birthday_check")
def handle_birthday_check(ack, body, respond):
    ack()
    user_id = body["user_id"]
    try:
        db = connect_db()
        cursor = db.cursor()
        cursor.execute(
            '''
            SELECT day, month, tz FROM birthday_info WHERE user_id = ?
            ''', (user_id,)
            )
        result = cursor.fetchone()
        db.close()
        print(result)
        if result:
            dd, mm, tz = result
            respond(f"You set your birthday as: {dd}/{mm} (Timezone: {tz})")
        else:
            respond("Your data doesn't exist yet.")
    except Exception:
        respond("There is a problem contact someone")
        return

@app.command("/birthday_delete")
def handle_birthday_delete(ack, body):
    ack()
    user_id = body["user_id"]
    app.client.chat_postMessage(
        channel=user_id,
        text="Are you sure you want to delete your birthday data?",
        blocks=[
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "Are you sure?"
                }
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "Yes, Delete it"
                        },
                        "style": "danger",
                        "action_id": "confirm_delete"
                    }
                ]
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "No"
                        },
                        "style": "primary",
                        "action_id": "cancel_delete"
                    }
                ]
            }
        ]
    )
    
    
@app.action("confirm_delete")
def handle_confirm_delete(ack, body, client, logger):
    ack()
    logger.info(body)
    channel_id = body["channel"]["id"]
    user_id = body["user"]["id"]
    ts = body["message"]["ts"]
    client.chat_update(channel=channel_id, ts=ts, text="Deleting your birthday data...")
    try:
        db = connect_db()
        cursor = db.cursor()
        cursor.execute(
        """
        DELETE FROM birthday_info WHERE user_id = ?
        """, (user_id,)
        )
        db.commit()
        db.close()
    except Exception as e:
        client.chat_postMessage(channel=channel_id, text="There was a problem deleting your data." + str(e))
    
@app.action("cancel_delete")
def handle_cancel_delete(ack, body, client, logger):
    ack()
    logger.info(body)
    channel_id = body["channel"]["id"]
    ts = body["message"]["ts"]
    client.chat_update(channel=channel_id, ts=ts, text="Ok not deleting anything.")



def find_and_send_wishes():
    now = datetime.now(pytz.utc)
    today = now.date()
    yesterday = today - timedelta(days=1)
    tomorrow = today + timedelta(days=1)
    db = connect_db()
    cursor = db.cursor()
    
    cursor.execute(
        '''
        SELECT user_id,day, month, tz FROM birthday_info WHERE
        (day = ? AND month = ?) OR
        (day = ? AND month = ?) OR
        (day = ? AND month = ?)
        ''', 
        (yesterday.day, yesterday.month,
        today.day, today.month,
        tomorrow.day, tomorrow.month)
    )
    results = cursor.fetchall()
    db.close()
    
    for (user_id,day, month, tz) in results:
        try:
            user_now = datetime.now(pytz.timezone(tz))
            if user_now.hour == 0 and user_now.day == day and user_now.month == month:
                app.client.chat_postMessage(
                    channel=user_id,
                    text="Happy Birthday!"
                )
            else:
                print(f"Not sending wish to {user_id} now, it's not midnight in their timezone.")
            
        except Exception as e:
            print(f"Error sending birthday wish to {user_id}: {e}")


schedule.every().hour.do(find_and_send_wishes)

def run_scheduler():
    while True:
        schedule.run_pending()
        time.sleep(60)
        
threading.Thread(target=run_scheduler, daemon=True).start()


if __name__ == "__main__":
    socketmodehandler =SocketModeHandler(app, APP_TOKEN)
    socketmodehandler.start()