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
ADMIN = os.getenv("ADMIN_USER_ID")
app = App(token=BOT_TOKEN)
client = WebClient(token=BOT_TOKEN)

init()



@app.command("/birthday_test")

def handle_birthday_test(ack, body, respond):
    ack()
    
    user_id = body["user_id"]

    if user_id != ADMIN:
        respond("This command is only available to administrators.")
        return
    text = body.get("text", "").strip()
    if text: 
        try:
            DD, MM = map(int, text. split("/"))
            test_day, test_month = DD, MM
        except:
            respond("Invalid format!  Use: `/birthday_test DD/MM` or leave empty for today")
            return
    else: 
        now = datetime.now()
        test_day, test_month = now.day, now.month
    
    db = connect_db()
    cursor = db.cursor()
    cursor.execute(
        '''
        SELECT user_id, tz FROM birthday_info WHERE day = ? AND month = ? 
        ''', (test_day, test_month)
    )
    results = cursor.fetchall()
    db.close()
    
    if not results: 
        respond(f"No birthdays registered for {test_day}/{test_month}")
        return
    
    respond(f"Starting test for {test_day}/{test_month} birthdays...")

    thread_ts = None
    if BIRTHDAY_CHANNEL:
        today_str = datetime.now().strftime('%Y-%m-%d')
        thread_ts = get_or_create_daily_thread(today_str)
    
    sent_dm_count = 0
    sent_channel_count = 0
    
    for test_user_id, tz in results:
        try:
            famous_person = get_random_famous(test_month, test_day)
            famous_text = format_birthday(famous_person)
            dm_message = f"""🎉🎂 *Happy Birthday! * 🎈🎁 (TEST)

Wishing you an amazing day filled with joy, laughter, and wonderful memories! 

From your Slack team! 🥳{famous_text}"""
            
            app.client. chat_postMessage(
                channel=test_user_id,
                text=dm_message
            )
            sent_dm_count += 1
            print(f"✅ Test DM sent to {test_user_id}")
            if thread_ts:
                send_birthday_to_thread(test_user_id, famous_person, thread_ts)
                sent_channel_count += 1
                print(f"✅ Test channel post sent for {test_user_id}")
            
        except Exception as e: 
            print(f"❌ Error sending test wish to {test_user_id}:  {e}")
    result_msg = f"*Test Complete!*\n\n"
    result_msg += f"Date tested: {test_day}/{test_month}\n"
    result_msg += f"DMs sent: {sent_dm_count}\n"
    
    if BIRTHDAY_CHANNEL:
        result_msg += f"Channel posts: {sent_channel_count}\n"
        if thread_ts:
            result_msg += f"Posted to thread in <#{BIRTHDAY_CHANNEL}>"
    else:
        result_msg += f"⚠️ Channel announcements disabled (BIRTHDAY_CHANNEL not set)"
    
    respond(result_msg)



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

def get_or_create_daily_thread(date_str):
    if not BIRTHDAY_CHANNEL:
        return None
    
    try:
        db = connect_db()
        cursor = db.cursor()
        cursor.execute(
            "SELECT thread_ts FROM birthday_threads WHERE date = ?  AND channel_id = ?",
            (date_str, BIRTHDAY_CHANNEL)
        )
        result = cursor.fetchone()
        
        if result:
            thread_ts = result[0]
            print(f"✅ Using existing thread for {date_str}")
        else:
            date_obj = datetime.strptime(date_str, '%Y-%m-%d')
            formatted_date = date_obj.strftime('%B %d, %Y')  # e.g., "December 29, 2025"
            
            response = app.client.chat_postMessage(
                channel=BIRTHDAY_CHANNEL,
                text=f"🎉🎂 *Birthdays Today - {formatted_date}* 🎈🎁",
                blocks=[
                    {
                        "type": "header",
                        "text": {
                            "type": "plain_text",
                            "text": f"🎉 Birthdays Today - {formatted_date}",
                            "emoji": True
                        }
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "Happy birthday to our amazing team members! 🥳\n_Check the thread below for individual wishes_ 👇"
                        }
                    }
                ]
            )
            
            thread_ts = response['ts']
            cursor.execute(
                """
                INSERT INTO birthday_threads (date, channel_id, thread_ts)
                VALUES (?, ?, ?)
                """,
                (date_str, BIRTHDAY_CHANNEL, thread_ts)
            )
            db.commit()
            print(f"✅ Created new thread for {date_str}")
        
        db.close()
        return thread_ts
        
    except Exception as e:
        print(f"Error managing thread:  {e}")
        if db:
            db.close()
        return None


def send_birthday_to_thread(user_id, famous_person, thread_ts):
    if not BIRTHDAY_CHANNEL or not thread_ts:
        return
    
    try:
        famous_text = ""
        if famous_person: 
            name = famous_person.get("name", "Unknown")
            year = famous_person.get("year", "")
            description = famous_person.get("description", "")
            
            famous_text = f"\n\n🌟 *You share your birthday with {name}"
            if year:
                famous_text += f" (born {year})"
            famous_text += "! *"
            
            if description: 
                sentences = description.split('. ')
                desc_short = sentences[0]
                if len(desc_short) > 200:
                    desc_short = desc_short[:197] + "..."
                elif not desc_short. endswith('.'):
                    desc_short += "."
                famous_text += f"\n_{desc_short}_"
        message = f"""🎂 Happy Birthday <@{user_id}>!  🎉

Wishing you an amazing day filled with joy, laughter, and wonderful memories!{famous_text}"""
        
        app.client.chat_postMessage(
            channel=BIRTHDAY_CHANNEL,
            thread_ts=thread_ts,
            text=message
        )
        print(f"✅ Posted birthday wish for {user_id} in thread")
        
    except Exception as e:
        print(f"Error posting to thread: {e}")


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
    
    print(f"Checking {len(results)} user(s)")
    thread_ts = None
    if BIRTHDAY_CHANNEL:
        today_str = today.strftime('%Y-%m-%d')
        thread_ts = get_or_create_daily_thread(today_str)
    
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
                famous_person = get_random_famous(month, day)
                famous_text = format_birthday(famous_person)
                dm_message = f"""🎉🎂 *Happy Birthday! * 🎈🎁

Wishing you an amazing day filled with joy, laughter, and wonderful memories! 
🥳{famous_text}"""
                app.client.chat_postMessage(
                    channel=user_id,
                    text=dm_message
                )
                print(f"✅ Sent DM to {user_id}")
                if thread_ts: 
                    send_birthday_to_thread(user_id, famous_person, thread_ts)
        
        except Exception as e:
            print(f"Error processing {user_id}: {e}")

def daily_cleanup():
    print(f"\nRunning daily cache cleanup at {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    deleted = clean(days=90)
    print(f"Cleaned {deleted} old entries")

schedule.every().day.at("03:00").do(daily_cleanup)
schedule.every().hour.do(find_and_send_wishes)

def run_scheduler():
    print("\nScheduler started!")
    print("  Birthday checks:  Every hour")
    print("  Cache cleanup: Daily at 03:00 UTC")
    print("  Thread cleanup: Daily at 03:00 UTC\n")
    while True:
        schedule.run_pending()
        time.sleep(60)
    
threading.Thread(target=run_scheduler, daemon=True).start()


if __name__ == "__main__":
    socketmodehandler =SocketModeHandler(app, APP_TOKEN)
    socketmodehandler.start()