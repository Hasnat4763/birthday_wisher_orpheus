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
from calling_api import get_random_famous, format_birthday, clean
dotenv.load_dotenv()

APP_TOKEN = os.getenv("APP_TOKEN")
BOT_TOKEN = os.getenv("BOT_TOKEN")
BIRTHDAY_CHANNEL = os.getenv("BIRTHDAY_CHANNEL_ID")

app = App(token=BOT_TOKEN)
client = WebClient(token=BOT_TOKEN)

init()



@app.command("/birthday_test")
def handle_birthday_test(ack, body, respond):
    ack()
    user_id = body["user_id"]
    now = datetime.now()
    day, month = now.day, now.month
    db = connect_db()
    cursor = db.cursor()
    cursor.execute(
        '''
        SELECT user_id, tz FROM birthday_info WHERE day = ? AND month = ?
        ''', (day, month)
    )
    results = cursor.fetchall()
    db.close()
    if not results:
        respond(f"No birthdays registered for today ({day}/{month})")
        return
    sent_count = 0
    for user_id, tz in results: 
        try:
            famous_person = get_random_famous(month, day)
            famous_text = format_birthday(famous_person)
            message = f"""🎉🎂 *Happy Birthday!* 🎈🎁 (TEST)
            Wishing you an amazing day filled with joy, laughter,
            and wonderful memories!🥳{famous_text}"""
            app. client.chat_postMessage(
                channel=user_id,
                text=message
            )
            sent_count += 1
            print(f"✅ Test wish sent to {user_id} (TZ: {tz})")
            
        except Exception as e: 
            print(f"❌ Error sending test wish to {user_id}:  {e}")
    
    respond(f"✅ Test complete! Sent {sent_count} birthday message(s).")
    



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
            INSERT OR REPLACE INTO birthday_info (user_id, day, month, tz)
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
    """Check for birthdays and send wishes"""
    now = datetime.now(pytz.utc)
    today = now.date()
    yesterday = today - timedelta(days=1)
    tomorrow = today + timedelta(days=1)
    
    print(f"\n🔍 Birthday check at {now.strftime('%Y-%m-%d %H:%M')} UTC")
    
    db = connect_db()
    cursor = db.cursor()
    
    cursor.execute(
        '''
        SELECT user_id, day, month, tz FROM birthday_info WHERE
        (day = ? AND month = ?) OR
        (day = ? AND month = ?) OR
        (day = ? AND month = ?)
        ''', 
        (yesterday.day, yesterday.month,
         today.day, today.month,
         tomorrow.day, tomorrow. month)
    )
    results = cursor.fetchall()
    db.close()
    
    print(f"📋 Checking {len(results)} user(s)")
    
    birthday_users = []  # Track who has birthdays today
    
    for (user_id, day, month, tz) in results:
        try:
            if tz:
                try:
                    user_timezone = pytz.timezone(tz)
                    user_now = datetime.now(user_timezone)
                except pytz.UnknownTimeZoneError:
                    print(f"⚠️ Unknown timezone '{tz}' for {user_id}")
                    user_now = datetime.now(pytz.utc)
            else:
                user_now = datetime.now(pytz.utc)
            
            if user_now.hour == 0 and user_now.day == day and user_now.month == month:
                # Get famous person
                famous_person = get_random_famous(month, day)
                famous_text = format_birthday(famous_person)
                
                # Send DM to birthday person
                dm_message = f"""🎉🎂 *Happy Birthday!* 🎈🎁

Wishing you an amazing day filled with joy, laughter, and wonderful memories! 

From your Slack team!  🥳{famous_text}"""
                
                app. client.chat_postMessage(
                    channel=user_id,
                    text=dm_message
                )
                print(f"✅ Sent DM to {user_id}")
                
                # Add to list for channel announcement
                birthday_users.append({
                    'user_id':  user_id,
                    'famous':  famous_person
                })
        
        except Exception as e:
            print(f"❌ Error processing {user_id}: {e}")
    
    # Send channel announcement if configured and there are birthdays
    if BIRTHDAY_CHANNEL and birthday_users: 
        send_channel_announcement(birthday_users)


def send_channel_announcement(birthday_users):
    """Send birthday announcement to public channel"""
    try:
        if len(birthday_users) == 1:
            user_id = birthday_users[0]['user_id']
            message = f"🎉🎂 Happy Birthday to <@{user_id}>! 🎈🎁\n\nWishing you an amazing day!"
        else:
            # Multiple birthdays
            users_mentions = ", ".join([f"<@{u['user_id']}>" for u in birthday_users])
            message = f"🎉🎂 Happy Birthday to {users_mentions}! 🎈🎁\n\nWishing you all an amazing day!"
        
        if BIRTHDAY_CHANNEL:
            app.client.chat_postMessage(
                channel=BIRTHDAY_CHANNEL,
                text=message
            )
        print(f"✅ Sent channel announcement for {len(birthday_users)} birthday(s)")
        
    except Exception as e: 
        print(f"❌ Error sending channel announcement: {e}")

def daily_cleanup():
    """Clean old cache entries daily"""
    print(f"\n🗑️ Running daily cache cleanup at {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    deleted = clean(days=90)
    print(f"✅ Cleaned {deleted} old entries")

schedule.every().day.at("03:00").do(daily_cleanup)
schedule.every().hour.do(find_and_send_wishes)

def run_scheduler():
    while True:
        schedule.run_pending()
        time.sleep(60)
        
threading.Thread(target=run_scheduler, daemon=True).start()


if __name__ == "__main__":
    socketmodehandler =SocketModeHandler(app, APP_TOKEN)
    socketmodehandler.start()