from telegram import *
from telegram.ext import *

import logging
import psycopg2
import pytz
from datetime import time
from difflib import SequenceMatcher

from shortcuts import *
from bus_data import *
from telegram_messages import *

# Tokens for telegram and LTA API
TOKEN = os.environ.get('TELEGRAM_TOKEN_KEY')
LTA_TOKEN_KEY = os.environ.get('LTA_TOKEN_KEY')

PORT = int(os.environ.get('PORT', '5000'))

# TODO: feedback photos
# TODO: schedule msg new format

# If using database from Heroku
if os.environ.get('DATABASE_URL'):
    postgres_url = os.environ.get('DATABASE_URL')
    conn = psycopg2.connect(postgres_url, sslmode='require')
# If using local database
else:
    conn = psycopg2.connect("dbname=telegram_bot "
                            "user=postgres "
                            "password=admin")
conn.autocommit = True
db = conn.cursor()

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)


def prevent_error(update: Update, context: CallbackContext):
    logger.info(context.error)


def start(update: Update, context: CallbackContext):
    """
    When user starts the bot, show location keyboard and add user id into database to keep record of who uses the bot
    """
    bot_typing(context.bot, update.message.chat_id)
    location_keyboard = KeyboardButton(text="Send Location 📍", request_location=True)
    reply_markup = ReplyKeyboardMarkup([[location_keyboard]], resize_keyboard=True, one_time_keyboard=True)
    update.message.reply_text(welcome_msg(), reply_markup=reply_markup)
    db.execute("INSERT INTO all_users VALUES (%s, %s, 'Yes') ON CONFLICT DO NOTHING",
               (update.message.chat_id, update.message.from_user.full_name))


def nearest_locations(update: Update, context: CallbackContext):
    """
    Show user nearby bus stops if user uses current live location
    """
    user_message = update.message.text
    bot_typing(context.bot, update.message.chat_id)
    if user_message is None:
        location = update.effective_message.location
        location = (location.latitude, location.longitude)
        nearest_bus_stops = list()
        send_message = "<b>Nearest Bus Stops:</b> \n\n" \
                       "Click on any of the bus stop codes\n" \
                       "below to get the bus arrival timings\n" \
                       "for that bus stop!\n\n"
        with open('bus_stops.txt', 'r') as r:
            for bus_stop in r.readlines():
                bus_stop_location = bus_stop.split(' | ', 5)
                distance = haversine(location[0], location[1], float(bus_stop_location[3]), float(bus_stop_location[4]))
                if distance <= 0.35:
                    bus_stop_location.append(str(distance))
                    nearest_bus_stops.append(bus_stop_location)

        nearest_bus_stops.sort(key=lambda x: x[-1])
        for nearest_bus_stop in nearest_bus_stops:
            send_message += "<b>{}</b>\n{} (/{})\n\n".format(nearest_bus_stop[2], nearest_bus_stop[1],
                                                             nearest_bus_stop[0])

        update.message.reply_text(send_message, parse_mode=ParseMode.HTML)

    elif user_message.replace('.', '').replace(',', '').replace(' ', '') == '/bus' or user_message == 'Change Stop':
        location_keyboard = KeyboardButton(text="Send Location 📍", request_location=True)
        reply_markup = ReplyKeyboardMarkup([[location_keyboard]], resize_keyboard=True, one_time_keyboard=True)
        update.message.reply_text("Share Location by manually typing in your location or press the 'Send Location 📍' "
                                  "keyboard button.", reply_markup=reply_markup)


def user_input(update: Update, context: CallbackContext):
    """
    Execute different functions according to what user has typed and the current state of feedback & schedules table
    """
    # state=1 means that bot is expecting a new name from user when users rename their bus stop
    db.execute("SELECT * FROM users WHERE user_id=%s AND state='1'", (update.message.chat_id,))
    renaming_bus_stop = db.fetchone()
    if renaming_bus_stop:
        if update.message.text == '/exit':
            db.execute("UPDATE users SET state='0' WHERE user_id=%s AND state='1'", (update.message.chat_id,))
            update.message.reply_text('Quit Renaming Bus Stop...')
        else:
            new_name = update.message.text.upper()
            update.message.reply_text("<b>Successful!</b>\nOriginal: <b>{}</b>\nNew: <b>{}</b>"
                                      .format(renaming_bus_stop[2], new_name), parse_mode=ParseMode.HTML)
            db.execute("UPDATE users SET new_description=%s, state='0' WHERE user_id=%s AND description=%s",
                       (new_name, update.message.chat_id, renaming_bus_stop[2]))
        return

    message = update.message.text.replace('/', '').lower()
    bot_typing(context.bot, update.message.chat_id)

    # state=1 means that bot is expecting a feedback from user
    db.execute("SELECT * FROM feedback WHERE user_id=%s AND state='1'", (update.message.chat_id,))
    user_feedback = db.fetchone()

    # state=1 means that bot is expecting a bus stop code from user to schedule a message
    db.execute("SELECT * FROM schedules WHERE user_id=%s AND state='1'", (update.message.chat_id,))
    schedule_bus_code = db.fetchone()

    # state=2 means that bot is expecting bus numbers from user to schedule a message
    db.execute("SELECT * FROM schedules WHERE user_id=%s AND state='2'", (update.message.chat_id,))
    schedule_buses = db.fetchone()

    # state=3 means that bot is expecting a time from user to schedule a message
    db.execute("SELECT * FROM schedules WHERE user_id=%s AND state='3'", (update.message.chat_id,))
    schedule_msg_time = db.fetchone()

    # Deal with user's feedback
    if user_feedback:
        # Ensure that user message is kind of appropriate. To be improved...
        if len(message) > 5:
            db.execute("UPDATE feedback SET user_feedback=%s, datetime=%s, state='0' WHERE user_id=%s AND state='1'",
                       (message, str(datetime.utcnow() + timedelta(hours=8)).split('.')[0],
                        update.message.chat_id))
            update.message.reply_text('Thank you for your feedback!')
        elif 'exit' in message:
            db.execute("DELETE FROM feedback WHERE user_id=%s AND state='1'", (update.message.chat_id,))
            update.message.reply_text('Quit Feedback Section...')
        else:
            update.message.reply_text('Please type in a feedback that is appropriate/longer.\n\n'
                                      'Click/Type /exit to stop giving feedback.')

    # Deals with bus stop code when user is scheduling message
    # Change state=2 for schedules table. Expecting user for a time to schedule the message next.
    elif schedule_bus_code:
        if (len(message) == 5) and message.isdigit():
            description = None
            with open('bus_stops.txt', 'r') as r:
                for bus_stop in r.readlines():
                    if bus_stop.split(' | ')[0] == message:
                        description = bus_stop.split(' | ', 3)[2]
                        break

            url = "http://datamall2.mytransport.sg/ltaodataservice/BusArrivalv2?BusStopCode={}".format(message)
            headers = {'AccountKey': LTA_TOKEN_KEY}
            response = requests.get(url, headers=headers).json()
            all_buses = response['Services']
            all_bus_services = list()
            # To get all the bus service number into a list
            for bus in all_buses:
                all_bus_services.append(bus['ServiceNo'])

            # bus_services_data is a string consisting of bus numbers separated by commas
            bus_services_data = ','.join(all_bus_services)
            if description:
                db.execute("SELECT * FROM schedules WHERE user_id=%s AND state='2'", (update.message.chat_id,))
                user = db.fetchall()
                # To delete any duplicates
                if user:
                    db.execute("DELETE FROM schedules WHERE user_id=%s AND state='2'", (update.message.chat_id,))

                bot_typing(context.bot, update.message.chat_id)

                # Keyboard display for all the bus numbers of a bus stop
                # Maximum number of columns per row is 3
                keyboard, sublist = list(), list()
                for bus_service in all_bus_services:
                    if len(sublist) < 3:
                        sublist.append(InlineKeyboardButton(bus_service, callback_data='bus_{}_{}'
                                                            .format(bus_service, bus_services_data)))
                    if len(sublist) == 3:
                        keyboard.append(sublist)
                        sublist = list()

                # Find the remainder number of bus number in the last row
                num_remaining = len(all_bus_services) % 3
                # Last row will consist of 2 bus numbers and a confirm button
                if num_remaining == 2:
                    keyboard.append([InlineKeyboardButton(all_bus_services[-2], callback_data='bus_{}_{}'.
                                                          format(all_bus_services[-2], bus_services_data)),
                                     InlineKeyboardButton(all_bus_services[-1], callback_data='bus_{}_{}'.
                                                          format(all_bus_services[-1], bus_services_data)),
                                     InlineKeyboardButton('Confirm', callback_data='confirm_bus_num')])
                # Last row will consist of 1 bus number and a confirm button
                elif num_remaining == 1:
                    keyboard.append([InlineKeyboardButton(all_bus_services[-1], callback_data='bus_{}_{}'.
                                                          format(all_bus_services[-1], bus_services_data)),
                                     InlineKeyboardButton('Confirm', callback_data='confirm_bus_num')])
                # Last row will consist of no bus number but only a confirm button
                else:
                    keyboard.append([InlineKeyboardButton('Confirm', callback_data='confirm_bus_num')])

                reply_markup = InlineKeyboardMarkup(keyboard)
                update.message.reply_text(schedule_bus_number(message, 'None'), reply_markup=reply_markup,
                                          parse_mode=ParseMode.HTML)

                db.execute("UPDATE schedules SET bus_stop_code=%s, description=%s, state='2' WHERE user_id=%s AND "
                           "state='1'", (message, description, update.message.chat_id))
            else:
                update.message.reply_text("Bus Stop Code {} is not valid. Please check again.\n\n"
                                          "Click/Type /exit to stop scheduling message.".format(message))

        elif 'exit' in message:
            update.message.reply_text('Quit Scheduling Message...')
            db.execute("DELETE FROM schedules WHERE user_id=%s AND state='1'", (update.message.chat_id,))
        else:
            update.message.reply_text('{} is not a valid bus stop code. Bus stop code should be 5 digits. Please try '
                                      'again!\n\nClick/Type /exit to stop scheduling message.'.format(message))

    # Raise alert if user has not confirmed the bus numbers for scheduling message
    elif schedule_buses:
        if 'exit' in message:
            update.message.reply_text('Quit Scheduling Message...')
            db.execute("DELETE FROM schedules WHERE user_id=%s AND state='2'", (update.message.chat_id,))
        else:
            update.message.reply_text('Please select your bus timings you want to be notified on.\n\n'
                                      'Click/Type /exit to stop scheduling message.')

    # Deals with time when user is scheduling message
    elif schedule_msg_time:
        # [0-9] means the character is a number from 0 to 9
        # ? means if the first number is 0 or 1, just take either, | means or operator
        time_format = re.compile("^([01]?[0-9]|2[0-3])[0-5][0-9]$")
        if re.search(time_format, message):
            db.execute("SELECT * FROM schedules WHERE user_id=%s AND state='3'", (update.message.chat_id,))
            bus_stop = db.fetchone()
            bus_stop_code, description = bus_stop[1], bus_stop[2]
            selected_buses = ''
            for bus in bus_stop[5:10]:
                # To check that it is not None or 'None'
                if type(bus) == str and bus != "None":
                    selected_buses += '{},'.format(bus)
            # If not bus is selected, all buses will be shown
            if selected_buses == '':
                selected_buses = 'ALL'
            else:
                # Remove the last comma
                selected_buses = selected_buses[:-1]
            update.message.reply_text(schedule_confirm(message, description, bus_stop_code, selected_buses),
                                      parse_mode=ParseMode.HTML)
            message = '{}:{}'.format(message[:2], message[-2:])
            db.execute("UPDATE schedules SET time=%s, state='0' WHERE user_id=%s AND state='3'",
                       (message, update.message.chat_id))
        elif 'exit' in message:
            update.message.reply_text('Quit Scheduling Message...')
            db.execute("DELETE FROM schedules WHERE user_id=%s AND state='3'", (update.message.chat_id,))
        else:
            update.message.reply_text(schedule_timing_failed(), parse_mode=ParseMode.HTML)

    else:
        # Assuming all bus codes have 5 digits
        if (len(message) == 5) and message.isdigit():
            description = None
            with open('bus_stops.txt', 'r') as r:
                for bus_stop in r.readlines():
                    bus_stop_location = bus_stop.split(' | ', 5)
                    if bus_stop_location[0] == message:
                        description = bus_stop_location[2]
                        latitude = float(bus_stop_location[3])
                        longitude = float(bus_stop_location[4])
                        break
            if description is not None:
                keyboard = [['Change Stop'], ['Add to Favourites ❤']]
                reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
                context.bot.send_location(chat_id=update.message.chat_id, latitude=latitude, longitude=longitude,
                                          reply_markup=reply_markup)

                bus_message = short_bus_timing_message(message)
                update.message.reply_text(bus_message[0], reply_markup=bus_message[1], parse_mode=ParseMode.HTML)

                db.execute('INSERT INTO bus_stop_code_history (user_id, bus_stop_code, description, datetime)'
                           'VALUES (%s, %s, %s, %s) ON CONFLICT (user_id, bus_stop_code) DO UPDATE SET '
                           'datetime=%s',
                           (update.message.chat_id, bus_message[3], description,
                            str(datetime.utcnow() + timedelta(hours=8)).split('.')[0],
                            str(datetime.utcnow() + timedelta(hours=8)).split('.')[0]))
            else:
                update.message.reply_text('{} is not a valid bus stop code. Please try again!'.format(message))

        # Assuming bus number has <=4 numbers/alphabets
        elif (len(message) <= 4) and has_numbers(message):
            bus_number_list = set()
            with open('bus_routes.txt', 'r') as r:
                for bus_stop in r.readlines():
                    bus_number_list.add(bus_stop.split(' | ')[0])

            if message in bus_number_list:
                keyboard = [[InlineKeyboardButton('Bus Routes', callback_data='callback_routes')]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                update.message.reply_text('Bus /{}'.format(message), reply_markup=reply_markup)
            else:
                update.message.reply_text('There is currently no data for bus number {}!'.format(message.upper()))

        # Assume user types in a location keyword
        elif re.sub('[^A-Za-z0-9]+', '', message).isalnum() and (len(message) >= 5):
            possible_locations = set()
            with open('bus_stops.txt', 'r') as r:
                for bus_stop in r.readlines():
                    attributes = bus_stop.split(' | ', 5)

                    # Find the similarity ratio between official road name and message
                    road_name = attributes[1]
                    s = SequenceMatcher(None, message, road_name.lower())
                    # Ratio must be above 75% for road name to be accepted
                    if s.ratio() > 0.75 or message in road_name.lower():
                        if len(possible_locations) <= 20:
                            possible_locations.add(bus_stop)

                    # Find the similarity ratio between official bus stop name and message
                    bus_stop_name = attributes[2]
                    s = SequenceMatcher(None, message, bus_stop_name.lower())
                    # Ratio must be above 75% for bus stop name to be accepted
                    if s.ratio() > 0.75 or message in bus_stop_name.lower():
                        if len(possible_locations) <= 20:
                            possible_locations.add(bus_stop)

            # If there is at least 1 location that matches what the user inputted
            if possible_locations:
                location_message = "<b>Possible Location:</b>\n\n" \
                                   "Click on any of the bus stop codes\n" \
                                   "below to get the bus arrival timings\n" \
                                   "for that bus stop!\n\n"

                for possible_location in possible_locations:
                    possible_location = possible_location.split(' | ', 5)
                    location_message += "<b>{}</b>\n{} (/{})\n\n".format(possible_location[2], possible_location[1],
                                                                         possible_location[0])
                keyboard = [['Change Stop'], ['Add to Favourites ❤']]
                reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
                update.message.reply_text(location_message, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
            else:
                update.message.reply_text(cannot_understand())
        # If bot cannot understand user's message
        else:
            update.message.reply_text(cannot_understand())


def show_favourites(update: Update, context: CallbackContext):
    """
    Show bus stop codes that users had previously added to favourites for convenience
    """
    bot_typing(context.bot, update.message.chat_id)
    db.execute('SELECT DISTINCT * FROM users WHERE user_id=%s', (update.message.chat_id,))
    favourites = db.fetchall()
    if favourites:
        for favourite in favourites:
            message = '<b>{}\nBus Stop Code: /{}</b>'.format(favourite[3], favourite[1])
            keyboard = [
                [InlineKeyboardButton('Select', callback_data='select_favourite'),
                 InlineKeyboardButton('Delete', callback_data='delete_favourite')],
                [InlineKeyboardButton('Rename', callback_data='rename_bus_stop')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            update.message.reply_text(message, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
    else:
        update.message.reply_text(no_fav_msg())


def add_favourites(update: Update, context: CallbackContext):
    """
    Allow users to add a new bus stop code to their favourites
    """
    bot_typing(context.bot, update.message.chat_id)
    try:
        message = update.message.text.split(' ')[1]
        if update.message.text == 'Add to Favourites ❤':
            db.execute('SELECT * FROM bus_stop_code_history WHERE user_id = %s ORDER BY datetime DESC',
                       (update.message.chat_id,))
            last_sent_code = db.fetchone()

            db.execute("INSERT INTO users (user_id, bus_stop_code, description, new_description, state) VALUES "
                       "(%s, %s, %s, %s, '0') ON CONFLICT (user_id, bus_stop_code) DO NOTHING",
                       (last_sent_code[0], last_sent_code[1], last_sent_code[2], last_sent_code[2]))

            update.message.reply_text(add_favourites_msg(last_sent_code[1]), parse_mode=ParseMode.HTML)

        elif len(message) == 5 and message.isdigit():
            with open('bus_stops.txt', 'r') as r:
                for bus_stop in r.readlines():
                    bus_stop_location = bus_stop.split(' | ', 5)
                    if bus_stop_location[0] == message:
                        description = bus_stop_location[2]
            db.execute("INSERT INTO users (user_id, bus_stop_code, description, new_description, state) VALUES "
                       "(%s, %s, %s, %s, '0') ON CONFLICT (user_id, bus_stop_code) DO NOTHING",
                       (update.message.chat_id, message, description, description))

            update.message.reply_text(add_favourites_msg(message), parse_mode=ParseMode.HTML)

        elif len(message) != 5 and not message.isdigit():
            update.message.reply_text(failed_add_fav_msg(message))
    except IndexError:
        update.message.reply_text(instructions_add_fav())


def buttons_functions(update: Update, context: CallbackContext):
    """
    Deals with inline keyboard button
    """
    # For bus timing messages
    if 'Wheel-chair Accessible' in update.callback_query.message['text']:
        bus_code = update.callback_query.message['text'].split('Bus Stop Code: /')[1][:5]
        display_format = update.callback_query.message['text'].split('Format: ')[1].split('\n')[0]
        if update.callback_query.data == 'callback_format':
            if display_format == 'Detailed':
                bus_message = short_bus_timing_message(bus_code)
            else:
                bus_message = long_bus_timing_message(bus_code)
        else:
            if display_format == 'Detailed':
                bus_message = long_bus_timing_message(bus_code)
            else:
                bus_message = short_bus_timing_message(bus_code)
        update.callback_query.edit_message_text(bus_message[0], reply_markup=bus_message[1], parse_mode=ParseMode.HTML)

    # To show list of all the bus stops of a bus service
    elif update.callback_query.data == 'callback_routes':
        bus_number = update.callback_query.message['text'].split('/')[1]
        message = '<b>Bus /{}</b>\n\n'.format(bus_number)
        direction1, direction2 = '', ''
        with open('bus_routes.txt', 'r') as r:
            for bus in r.readlines():
                attributes = bus.split(' | ', 9)
                if bus_number == attributes[0]:
                    if attributes[1] == '1':
                        direction1 += '{} (/{})\n'.format(attributes[3], attributes[2])
                    if attributes[1] == '2':
                        direction2 += '{} (/{})\n'.format(attributes[3], attributes[2])

        first_stop = direction1.split('(')[0]
        direction1 = '<b>From {}:</b>\n{}'.format(first_stop, direction1)

        if direction2:
            first_stop = direction2.split('(')[0]
            direction2 = '\n\n<b>From {}:</b>\n{}'.format(first_stop, direction2)
        update.effective_message.reply_text(message+direction1+direction2, parse_mode=ParseMode.HTML)

    # To allow users to select their favourite bus stop code
    elif update.callback_query.data == 'select_favourite':
        bus_timings = short_bus_timing_message(update.callback_query.message['text'].split('/')[-1])
        update.callback_query.edit_message_text(bus_timings[0], reply_markup=bus_timings[1], parse_mode=ParseMode.HTML)

    # To allow users to delete their favourite bus stop code
    elif update.callback_query.data == 'delete_favourite':
        bus_stop_code = update.callback_query.message['text'].rsplit('/')[-1]
        db.execute('DELETE FROM users WHERE user_id=%s AND bus_stop_code=%s', (update.callback_query.message.chat_id,
                                                                               bus_stop_code))
        update.callback_query.edit_message_text(delete_fav_msg(bus_stop_code))

    # To allow users to rename their favourite bus stop
    elif update.callback_query.data == 'rename_bus_stop':
        bus_stop_code = update.callback_query.message['text'].rsplit('/')[-1]
        db.execute("UPDATE users SET state='1' WHERE user_id=%s AND bus_stop_code=%s RETURNING description, "
                   "new_description",
                   (update.callback_query.message.chat_id, bus_stop_code))
        descriptions = db.fetchone()
        description, new_description = descriptions[0], descriptions[1]
        if description == new_description:
            update.effective_message.reply_text('<b>Renaming in process:</b>\nPlease rename <b>{}</b>.\n\nClick/Type '
                                                '/exit to stop renaming.'
                                                .format(description), reply_markup=ForceReply(),
                                                parse_mode=ParseMode.HTML)
        else:
            update.effective_message.reply_text('<b>Renaming in process:</b>\nOriginal: <b>{}</b>.\nCurrent: <b>{}</b>.'
                                                '\n\nClick/Type /exit to stop renaming'
                                                .format(description, new_description), reply_markup=ForceReply(),
                                                parse_mode=ParseMode.HTML)

    # To allow users to schedule a message
    elif update.callback_query.data == 'schedule_message':
        update.effective_message.reply_text('Enter 5 digit bus stop code:\ne.g: 14141\n\n'
                                            'Click/Type /exit to stop scheduling message.', reply_markup=ForceReply())
        db.execute("INSERT INTO schedules (user_id, bus_stop_code, time, state) VALUES (%s, '-', '-', 1) ON CONFLICT "
                   "(user_id, bus_stop_code, time, state) DO NOTHING", (update.effective_message.chat_id,))

    # To allow users to view their schedules
    elif update.callback_query.data == 'view_schedules':
        db.execute("SELECT * FROM schedules WHERE user_id=%s AND state='0'", (update.effective_message.chat_id,))
        schedules = db.fetchall()
        # TODO: show buses that are being scheduled
        if schedules:
            update.effective_message.reply_text('View Scheduled Messages')
        else:
            update.effective_message.reply_text('No Scheduled Messages.\n\nTo schedule a message, click on the '
                                                '"Schedule Message" button.')
        for index, schedule in enumerate(schedules):
            # To check that buses_selected is not None or 'None'
            buses_selected = ','.join("".join(str(elem)) for elem in schedule[5:10] if type(elem) == str and
                                      elem != 'None')
            if buses_selected == '':
                buses_selected = 'ALL'
            keyboard = [[InlineKeyboardButton('Remove', callback_data='remove_scheduled_message-{}'
                                              .format(schedule[3]))]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            update.effective_message.reply_text(view_schedules(schedule[2], schedule[1], buses_selected, schedule[3]),
                                                reply_markup=reply_markup, parse_mode=ParseMode.HTML)

    # To allow users to delete their schedules
    elif 'remove_scheduled_message' in update.callback_query.data:
        data = update.callback_query.data
        msg_time = data.split('-')[1]

        message = update.effective_message.text
        bus_stop = message.split(':')[1].split('\n')[0][1:]

        db.execute('DELETE FROM schedules WHERE user_id=%s AND time=%s', (update.effective_message.chat['id'],
                                                                          msg_time))
        update.callback_query.edit_message_text("Schedule for {} removed.\n\nTo schedule a new message, click on the "
                                                "'Schedule Message' button in /settings!".format(bus_stop))

    # User chooses the bus number they want to see when they schedule message
    elif update.callback_query.data.startswith('bus_'):
        # Bus number that user selected mostly recently
        bus_number = update.callback_query.data.split('_')[1]
        # All the bus numbers that user had selected previously
        bus_services_data = update.callback_query.data.split('_')[2]
        # Convert all the bus numbers that user had selected previously into list
        all_bus_services = bus_services_data.split(',')

        keyboard, sublist = list(), list()

        for bus_service in all_bus_services:
            if len(sublist) < 3:
                sublist.append(InlineKeyboardButton(bus_service, callback_data='bus_{}_{}'.format(bus_service,
                                                                                                  bus_services_data)))
            if len(sublist) == 3:
                keyboard.append(sublist)
                sublist = list()

        num_rows = len(all_bus_services) % 3
        if num_rows == 2:
            keyboard.append([InlineKeyboardButton(all_bus_services[-2],
                                                  callback_data='bus_{}_{}'.format(all_bus_services[-2],
                                                                                   bus_services_data)),
                             InlineKeyboardButton(all_bus_services[-1],
                                                  callback_data='bus_{}_{}'.format(all_bus_services[-1],
                                                                                   bus_services_data)),
                             InlineKeyboardButton('Confirm', callback_data='confirm_bus_num')])
        elif num_rows == 1:
            keyboard.append([InlineKeyboardButton(all_bus_services[-1],
                                                  callback_data='bus_{}_{}'.format(all_bus_services[-1],
                                                                                   bus_services_data)),
                             InlineKeyboardButton('Confirm', callback_data='confirm_bus_num')])
        else:
            keyboard.append([InlineKeyboardButton('Confirm', callback_data='confirm_bus_num')])
        reply_markup = InlineKeyboardMarkup(keyboard)

        message = update.effective_message.text
        all_selected_buses = message.split(':')[-1]
        bus_stop_code = message.strip('Bus Stop Code ')[:5]
        # If user previously does not have any selected bus
        if 'None' in all_selected_buses:
            selected_bus = bus_number

        # If user removes a bus and there is no selected bus now
        elif bus_number == all_selected_buses or bus_number == all_selected_buses[1:]:
            selected_bus = 'None'

        # If user removes a bus and there are still other selected buses
        elif bus_number in all_selected_buses.split(','):
            buses = all_selected_buses.split(',')
            buses.remove(bus_number)
            selected_bus = ','.join(buses)

        # If user selects a new bus number
        else:
            selected_bus = "{},{}".format(all_selected_buses, bus_number)

        # Remove the extra comma in front if user removes the first bus he has selected
        if selected_bus[0] == ',':
            selected_bus = selected_bus[1:]
        if len(selected_bus.split(',')) > 5:
            selected_bus = selected_bus.split(',', 1)[1]
        update.effective_message.edit_text(schedule_bus_number(bus_stop_code, selected_bus),
                                           parse_mode=ParseMode.HTML, reply_markup=reply_markup)

    # After users confirm the bus number to be scheduled
    elif update.callback_query.data == 'confirm_bus_num':
        bus_stop_code = update.effective_message.text.strip('Bus Stop Code ')[:6]
        # Convert into tuple format for inserting into database
        selected_buses = tuple(update.effective_message.text.split(':')[1].split(","))
        # If at least a bus is selected previously
        if selected_buses != ('None',):
            while len(selected_buses) != 5:
                selected_buses += ('None',)

            update.effective_message.edit_text(schedule_timing(bus_stop_code), reply_markup=None,
                                               parse_mode=ParseMode.HTML)

            db.execute("SELECT * FROM schedules WHERE user_id=%s AND state='2'", (update.effective_message.chat_id,))
            user = db.fetchone()
            # Get the first 4 elements of the user
            # Find a better way to code this... UPDATE AND ON CONFLICT not allowed
            selected_buses = user[0:4] + ('3',) + selected_buses
            db.execute("DELETE FROM schedules WHERE user_id=%s AND state='2'", (update.effective_message.chat_id,))
            db.execute("INSERT INTO schedules VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT "
                       "(user_id, bus_stop_code, time, state) DO NOTHING", selected_buses)

        # If user did not select a bus - default option (ALL BUS SELECTED)
        else:
            update.effective_message.edit_text(schedule_timing(bus_stop_code), reply_markup=None,
                                               parse_mode=ParseMode.HTML,)
            db.execute("UPDATE schedules SET state='3' WHERE user_id=%s AND state='2'",
                       (update.effective_message.chat_id, ))

    # User chooses to receive MRT alerts during MRT breakdowns/delays
    elif update.callback_query.data == 'accept_mrt_alerts':
        keyboard = [[InlineKeyboardButton('Yes', callback_data='accept_mrt_alerts'),
                     InlineKeyboardButton('No', callback_data='reject_mrt_alerts')]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        update.effective_message.edit_text('Do you want to receive MRT alert messages in the event of MRT '
                                           'breakdowns/delays?\n\nYour current answer is: <b>Yes</b>',
                                           reply_markup=reply_markup, parse_mode=ParseMode.HTML)
        db.execute("UPDATE all_users SET receive_alerts='Yes' WHERE user_id=%s", (update.effective_message.chat_id, ))

    # User chooses not to receive MRT alerts during MRT breakdowns/delays
    elif update.callback_query.data == 'reject_mrt_alerts':
        keyboard = [[InlineKeyboardButton('Yes', callback_data='accept_mrt_alerts'),
                     InlineKeyboardButton('No', callback_data='reject_mrt_alerts')]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        update.effective_message.edit_text('Do you want to receive MRT alert messages in the event of MRT '
                                           'breakdowns/delays?\n\nYour current answer is: <b>No</b>',
                                           reply_markup=reply_markup, parse_mode=ParseMode.HTML)
        db.execute("UPDATE all_users SET receive_alerts='No' WHERE user_id=%s", (update.effective_message.chat_id, ))

    # To update users on any mrt alerts
    elif update.callback_query.data == 'mrt_alert':
        update.effective_message.reply_text(get_mrt_alerts(), parse_mode=ParseMode.HTML)

    # To send users an image of the mrt map
    elif update.callback_query.data == 'mrt_map':
        context.bot.send_photo(chat_id=update.effective_message.chat_id, photo=open('mrt_image.jpg', 'rb'))


def feedback(update: Update, context: CallbackContext):
    """
    Prompt user to input a feedback and add user's state to 1 in feedback table
    """
    bot_typing(context.bot, update.message.chat_id)
    update.message.reply_text(prompt_feedback_msg())
    db.execute("INSERT INTO feedback (user_id, user_feedback, datetime, state) VALUES (%s, '-', '-', '1') ON CONFLICT "
               "(user_id, user_feedback, datetime, state) DO NOTHING", (update.message.chat_id,))


def settings(update: Update, context: CallbackContext):
    """
    Settings to schedule new message or view schedules messages / opt in or out of MRT alert messages
    """
    bot_typing(context.bot, update.message.chat_id)
    keyboard = [[InlineKeyboardButton('Schedule Message', callback_data='schedule_message')],
                [InlineKeyboardButton('View Scheduled Messages', callback_data='view_schedules')]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    update.message.reply_text('Set reminders for your bus timings at a scheduled time daily!',
                              reply_markup=reply_markup)

    db.execute("SELECT * FROM all_users WHERE user_id=%s", (update.message.chat_id, ))
    option = db.fetchone()[2]

    keyboard = [[InlineKeyboardButton('Yes', callback_data='accept_mrt_alerts'),
                 InlineKeyboardButton('No', callback_data='reject_mrt_alerts')]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    update.message.reply_text('Do you want to receive MRT alert messages in the event of MRT breakdowns/delays?\n\n'
                              'Your current answer is: <b>{}</b>'.format(option),
                              reply_markup=reply_markup, parse_mode=ParseMode.HTML)


def view_mrt(update: Update, context: CallbackContext):
    """
    Allow users to be alerted when there is a MRT delay/breakdown. MRT map is also included for reference
    """
    bot_typing(context.bot, update.message.chat_id)
    keyboard = [[InlineKeyboardButton('MRT Alerts', callback_data='mrt_alert'),
                 InlineKeyboardButton('MRT Map', callback_data='mrt_map')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text('Note that MRT Service Alerts will only be activated if there are breakdowns',
                              reply_markup=reply_markup)


# def photo(update: Update, context: CallbackContext):
#     db.execute("SELECT * FROM feedback WHERE user_id=%s AND state='1'", (update.message.chat_id,))
#     if db.fetchone() is not None:
#         photo_file = update.message.photo[-1].get_file()
#
#         photo_file.download('user_photo.jpg')
#         if os.path.exists('user_photo.jpg'):
#             with open('user_photo.jpg', 'rb') as file:
#                 blob_photo = file.read()
#             db.execute("INSERT INTO feedback (user_id, image) VALUES (%s, %s)", (update.message.chat_id, blob_photo))
#             update.message.reply_text('Thank you for your feedback. We will look into it as soon as possible!')
#         os.remove('user_photo.jpg')


def send_scheduled_msg(context: CallbackContext):
    """
    This function is being called every minute to send bus arrival timings to users if they schedule it
    """
    # Time format is 21:54
    db.execute("SELECT * FROM schedules WHERE time=%s", (str(datetime.utcnow() + timedelta(hours=8)).split(' ')[1].
                                                         rsplit(':', 1)[0],))
    users = db.fetchall()

    for user in users:
        buses_selected_list = list(filter(lambda x: type(x) == str and x != 'None', user[5:10]))
        bus_message = scheduled_bus_timing_format(user[1], buses_selected_list)
        context.bot.send_message(chat_id=user[0], text=bus_message[0], reply_markup=bus_message[1],
                                 parse_mode=ParseMode.HTML)


def update_mrt_alert(context: CallbackContext):
    """
    This function is being called every 10 minutes to check for MRT alerts.
    If there is a new alert message, send it to all users
    """
    db.execute("SELECT * FROM mrt_updates ORDER BY datetime DESC")
    latest_msg = db.fetchone()
    # If latest_msg is not None. None occurs when mrt_updates table is empty
    if latest_msg is not None:
        latest_msg = latest_msg[0]

    if get_mrt_alerts() != latest_msg and get_mrt_alerts() != 'All Train Services Working Normally 👍':
        db.execute("SELECT * FROM all_users WHERE receive_alerts='Yes'")
        users = db.fetchall()
        for user in users:
            context.bot.send_message(chat_id=user[0], text=get_mrt_alerts())
        db.execute("INSERT INTO mrt_updates VALUES (%s, %s) ON CONFLICT (message) DO NOTHING",
                   (get_mrt_alerts(), str(datetime.utcnow() + timedelta(hours=8)).split('.')[0]))


def update_bus_data(context: CallbackContext):
    """
    This function is being called daily at 23:00 SGT to update bus routes and bus stops
    """
    logger.info("Updating Bus Route Now...")
    bus_routes()
    logger.info("Updating Bus Data Now...")
    update_bus_stops()
    logger.info("All updates complete")


def help_command(update: Update, context: CallbackContext):
    bot_typing(context.bot, update.message.chat_id)
    update.message.reply_text('Help!')


def bot_typing(bot, chat_id):
    """
    To stimulate human typing action
    """
    bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)


def stop(update: Update, context: CallbackContext):
    """
    When user stops the bot
    """
    bot_typing(context.bot, update.message.chat_id)
    user = update.message.from_user
    logger.info("User %s canceled the conversation.", user.first_name)
    update.message.reply_text(stop_bot_msg(), reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END


def main():
    updater = Updater(TOKEN, use_context=True)
    dispatcher = updater.dispatcher
    job = updater.job_queue

    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("help", help_command))
    dispatcher.add_handler(CommandHandler("bus", nearest_locations))
    dispatcher.add_handler(MessageHandler(Filters.location, nearest_locations))
    dispatcher.add_handler(CallbackQueryHandler(buttons_functions))
    dispatcher.add_handler(MessageHandler(Filters.location, buttons_functions))
    dispatcher.add_handler(CommandHandler("favourites", show_favourites))
    dispatcher.add_handler(CommandHandler("add_favourites", add_favourites))
    # dispatcher.add_handler(MessageHandler(Filters.photo, photo))
    dispatcher.add_handler(CommandHandler("feedback", feedback))
    dispatcher.add_handler(CommandHandler("settings", settings))
    dispatcher.add_handler(CommandHandler("stop", stop))
    dispatcher.add_handler(CommandHandler('mrt', view_mrt))
    dispatcher.add_handler(MessageHandler(Filters.command, user_input))
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.regex('^(Change Stop|Add to Favourites ❤|mrt|'
                                                                        'Schedule Message|'
                                                                        'View Scheduled Messages)$'), user_input))
    dispatcher.add_handler(MessageHandler(Filters.text & Filters.regex('^Change Stop$'), nearest_locations))
    dispatcher.add_handler(MessageHandler(Filters.text & Filters.regex('^Add to Favourites ❤$'), add_favourites))
    dispatcher.add_error_handler(prevent_error)

    job.run_repeating(send_scheduled_msg, interval=60)
    job.run_repeating(update_mrt_alert, interval=620)
    job.run_daily(update_bus_data,
                  time=time(hour=21, minute=00, second=00, tzinfo=pytz.timezone('Asia/Singapore')),
                  days=(0, 1, 2, 3, 4, 5, 6))

    if os.environ.get('DATABASE_URL'):
        updater.start_webhook(listen="0.0.0.0", port=int(PORT), url_path=TOKEN)

        updater.bot.setWebhook('https://sg-bus-telegram-bot.herokuapp.com/' + TOKEN)
        updater.idle()
    else:
        updater.start_polling()


if __name__ == '__main__':
    main()
