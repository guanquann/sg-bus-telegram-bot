"""
Messages that Telegram Bot will send according to user's message/input
"""


def welcome_msg():
    """
    Instructions to welcome users to bot.
    """
    return 'Welcome! This is a Singapore Bus Bot.\n\n' \
           'You can send me your: \n' \
           '   1. Bus Number \n' \
           '   2. Bus Stop Code \n' \
           '   3. Location\n' \
           'And I would inform you your bus arrival timings! Simple right?\n\n' \
           'To see what else can this bot do, type "/" and select the command you would like to run.\n' \
           'Use /stop to stop the bot.'


def cannot_understand():
    """
    Message that will be sent if bot cannot understand user's input/message
    """
    return 'Sorry😣! We could not understand what you just said.\n\n' \
           'If you had typed a bus stop code, ensure that it is 5 digits.\n    e.g: 67729 \n\n' \
           'If you had typed a bus number, ensure that it is less than 5 digits/alphabets.\n    e.g: 88 \n\n' \
           'If you had typed a location, ensure that it is more specific and accurate. \n    ' \
           'e.g: Sengkang East Ave, not Singkang E'


def add_favourites_msg(bus_stop_code):
    """
    Message that will be sent if user add a bus stop code to their favourites
    """
    return 'Bus Stop Code /{} has been added to your favourites! \n' \
           'To view all your favourites, ' \
           'type: /favourites'.format(bus_stop_code)


def failed_add_fav_msg(bus_stop_code):
    """
    Message that will be sent if user gives an invalid bus stop code and tries to add it to favourites
    """
    return '{} is not a valid Bus Stop Code! \n\nTo add to favourites, ' \
           'type: /add_favourites [BUS STOP CODE]\n\n  e.g: /add_favourites 14141'.format(bus_stop_code)


def delete_fav_msg(bus_stop_code):
    """
    Message that will be sent if user delete a bus stop code from their favourites
    """
    return 'Bus Stop Code /{} has been deleted! \n\n' \
           'To add another bus stop code, type: /add_favourites [BUS STOP CODE]' \
           '\n\n  e.g: /add_favourites 14141'.format(bus_stop_code)


def no_fav_msg():
    """
    Message that will be sent if user types '/favourites' but he/she has no favourite bus stop code yet
    """
    return 'You do not have any favourite bus stop code.\n\n' \
           'To add a bus stop code to favourites, type: /add_favourites [BUS STOP CODE]\n\n  ' \
           'e.g: /add_favourites 14141\n\nAlternatively, you can type in your bus stop code ' \
           'and click on the "Add to Favourites ❤" KeyBoard Button!'


def instructions_add_fav():
    """
    Instructions that will be sent to help users add their favourite bus stop code
    """
    return 'To add a bus stop code to favourites, type: /add_favourites [BUS STOP CODE]\n\n  ' \
           'e.g: /add_favourites 14141\n\nAlternatively, you can type in your bus stop code ' \
           'and click on the "Add to Favourites ❤" KeyBoard Button!'


def view_schedules(description, bus_stop_code, bus_selected, time):
    """
    Message that will be sent when user wants to view their scheduled messages

    """
    return '<b>Bus Stop: </b>{}\n<b>Bus Stop Code: </b>/{}\n<b>Buses: </b>{}<b>\nTime:</b> {}H\n' \
           '<b>Frequency:</b> Daily'.format(description, bus_stop_code, bus_selected, time)


def schedule_bus_number(bus_stop_code, bus_selected):
    """
    Message that will be sent when user wants to choose bus for their scheduled messahes
    :return:
    """
    return 'Bus Stop Code <b>{}</b>\nYou can select the bus numbers that you want to receive their arrival timings.' \
           '\n\nIf you did not select any, all bus timings will be shown on the scheduled message.\n\n' \
           'You can select up to 5 buses per message.\n\nClick confirm after selecting your bus numbers.\n\n' \
           'Click/Type /exit to stop scheduling message.\n\n<b>Bus Selected:{}</b>'.format(bus_stop_code, bus_selected)


def schedule_timing(bus_stop_code):
    """
    Message that will be sent after user types in bus stop code when scheduling message
    :param bus_stop_code: Bus Stop Code of what users type in when scheduling message
    """
    return 'Bus Stop Code <b>{}</b>\nPlease type in the time you want your message to ' \
           'be scheduled. Time should strictly follow the 24 hr format shown below.\n\n' \
           'Type <b>0630</b> to represent 6:30AM.\nType <b>1930</b> to represent 7:30PM.' \
           '\n\nClick/Type /exit to stop scheduling message.'.format(bus_stop_code)


def schedule_confirm(message, description, bus_stop_code, selected_buses):
    """
    Message that will be sent to user once they confirm their schedule
    :param message: Time
    :param description: Bus Stop Name
    :param bus_stop_code: Bus Stop Code
    :param selected_buses: Bus selected for scheduling message
    :return:
    """
    return 'You will receive message at {}H for <b>{} (/{})</b>.\n\nBus: <b>{}</b>\n\n' \
           'You can view all your schedules at /settings and clicking the "View Scheduled Message" button'.\
        format(message, description, bus_stop_code, selected_buses)


def schedule_timing_failed():
    """
    Message that will be sent if user types in an incorrect time format
    """
    return 'Invalid time format. Time should strictly follow the 24 hr format shown below.' \
           '\n\nType <b>0630</b> to represent 6:30AM.\nType <b>1930</b> to represent ' \
           '7:30PM.\n\nClick/Type /exit to stop scheduling message.'


def mrt_alert_msg(mrt_line, direction, stations, public_bus, mrt_shuttle, mrt_shuttle_dir):
    """
    Message that will be sent if there is an MRT alert/breakdown/delay
    :param mrt_line: "DTL/NSL/EWL..."
    :param direction: "Both"/specific MRT station name("Jurong East")
    :param stations: "NS17, NS16, NS15, NS14, NS13, NS12..."
    :param public_bus: "Free bus service island-wide..."
    :param mrt_shuttle: "EW21|CC22, EW23, EW24|NS1, EW27..."
    :param mrt_shuttle_dir: "Both"
    """
    return '<b>Line:</b> {}\n<b>Direction:</b> {}\n<b>Stations:</b> {}\n' \
           '<b>Free Public Bus:</b> {}\n<b>Free MRT Shuttle:</b> {}\n' \
           '<b>MRT Shuttle Direction:</b> {}\n\n'.format(mrt_line, direction, stations, public_bus,
                                                         mrt_shuttle, mrt_shuttle_dir)


def prompt_feedback_msg():
    """
    Message that will be sent if user types '/feedback'
    """
    return 'Please type in your feedback if there are any bugs/problems and ' \
           'we will look into it ASAP!\n\nClick/Type /exit to stop giving feedback.'


def stop_bot_msg():
    """
    Message that will be sent if user stops the bot
    """
    return 'Bye! \n' \
           'You can use /start to start the bot again. \n' \
           'We hope to see you again :)'
