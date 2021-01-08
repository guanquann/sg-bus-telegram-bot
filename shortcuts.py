import os
import re
import requests

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram_messages import *

from math import cos, sin, asin, sqrt, radians
from datetime import datetime, timedelta
import holidays

# Tokens for telegram and LTA API
TOKEN = os.environ.get('TELEGRAM_TOKEN_KEY')
LTA_TOKEN_KEY = os.environ.get('LTA_TOKEN_KEY')


def time_difference(bus_stop_code, bus_num, arrival_time):
    """
    Find the time difference between current time and bus arrival
    :param str bus_stop_code: Bus Stop Code of bus stop
    :param str bus_num: Bus Number
    :param str arrival_time: Arrival time for bus to reach bus stop
    :return: Difference in time in minutes/No Estimation/Not in Operation
    """
    if arrival_time != '':
        arrival_time = datetime.strptime(arrival_time.split('+')[0].replace('T', ' '), '%Y-%m-%d %H:%M:%S')
        difference = round(((arrival_time - (datetime.utcnow() + timedelta(hours=8))).total_seconds() / 60.0))
        return difference

    else:
        # Bus is in operation, but arrival data not available: No Estimation
        # Bus not in operation and arrival data not available: Not in Operation
        day = datetime.today().weekday()
        if datetime.now() in holidays.Singapore():
            first_bus_index = 8
            last_bus_index = 9
        elif day < 5:
            first_bus_index = 4
            last_bus_index = 5
        else:
            first_bus_index = 6
            last_bus_index = 7
        with open('bus_routes.txt', 'r') as r:
            first_bus_timing = '0000'
            last_bus_timing = '1900-01-01 2359'
            for bus in r.readlines():
                attributes = bus.split(' | ', 9)
                if attributes[0] == bus_num and attributes[2] == bus_stop_code:
                    first_bus_timing = attributes[first_bus_index]
                    last_bus_timing = attributes[last_bus_index]
                    if attributes[last_bus_index] < '1200':
                        last_bus_timing = '1900-01-02 {}'.format(last_bus_timing)
                    elif attributes[last_bus_index] >= '1200':
                        last_bus_timing = '1900-01-01 {}'.format(last_bus_timing)
                break
        time_format = '%H%M'
        current_time = str(datetime.utcnow() + timedelta(hours=8)).split()[1][:5].replace(':', '')
        if datetime.strptime(first_bus_timing, time_format) < datetime.strptime(current_time, time_format) < \
                datetime.strptime(last_bus_timing, '%Y-%m-%d %H%M'):
            return 'No Estimation'
        else:
            return 'Not In Operation ❌'


def haversine(current_lat, current_lon, bus_stop_lat, bus_stop_lon):
    """
    Haversine Formula: Calculate the  circle distance between two points on Earth
    :param str current_lat: Latitude of user's location
    :param str current_lon: Longitude of user;s location
    :param float bus_stop_lat: Latitude of bus stop
    :param float bus_stop_lon: Longitude of bus stop
    :return: Distance between user's current location and bus stop
    """

    # convert decimal degrees to radians
    lon1, lat1, lon2, lat2 = map(radians, [current_lon, current_lat, bus_stop_lon, bus_stop_lat])

    diff_lon = lon2 - lon1
    diff_lat = lat2 - lat1
    a = sin(diff_lat/2)**2 + cos(lat1) * cos(lat2) * sin(diff_lon/2)**2
    c = 2 * asin(sqrt(a))

    # Radius of earth in kilometers. Use 3956 for miles
    r = 6371
    return c * r


def has_numbers(string):
    """
    Check if user's message has a number
    :param string: User's message
    :return: True/False (boolean)
    """
    return bool(re.search(r'\d', string))


def get_bus_timing(bus_stop_code):
    """
    Get all the bus timings of a bus stop
    :param bus_stop_code: Bus Stop Code of a bus stop
    :returns: Bus timings of a bus stop, Bus Stop Name, Bus Stop Code
    """
    url = "http://datamall2.mytransport.sg/ltaodataservice/BusArrivalv2?BusStopCode={}".format(bus_stop_code)
    headers = {'AccountKey': LTA_TOKEN_KEY}
    response = requests.get(url, headers=headers).json()
    all_buses = response['Services']

    bus_timings = list()
    for bus in all_buses:
        print(bus)
        try:
            bus_timings.append([bus['ServiceNo'],
                                [time_difference(bus_stop_code, bus['ServiceNo'], bus['NextBus']['EstimatedArrival']),
                                 bus['NextBus']['Load'],
                                 bus['NextBus']['Feature']],
                                [time_difference(bus_stop_code, bus['ServiceNo'], bus['NextBus2']['EstimatedArrival']),
                                 bus['NextBus2']['Load'],
                                 bus['NextBus2']['Feature']],
                                [time_difference(bus_stop_code, bus['ServiceNo'], bus['NextBus3']['EstimatedArrival']),
                                 bus['NextBus3']['Load'],
                                 bus['NextBus3']['Feature']]])
        except ValueError:
            print('error')

    with open('bus_stops.txt', 'r') as r:
        for bus_stop in r.readlines():
            number_code = bus_stop.split(' | ', 5)[0]
            bus_stop_name = bus_stop.split(' | ', 5)[2]
            if bus_stop_code == number_code:
                break
    return bus_timings, bus_stop_name, bus_stop_code


def long_bus_timing_message(bus_stop_code):
    """
    Create detailed bus timing message for user in Telegram
    :param bus_stop_code: Bus Stop Code of a bus stop
    :returns: Bus Message, reply_markup, Bus Stop Name, Bus Stop Code
    """
    bus_timings, bus_stop_name, bus_stop_code = get_bus_timing(bus_stop_code)
    bus_message = '<b>Bus Stop: </b>{}\n<b>Bus Stop Code: </b>/{}\n\n'.format(bus_stop_name, bus_stop_code)
    for bus in bus_timings:
        for bus_timings in bus:
            if isinstance(bus_timings, list):
                if type(bus_timings[0]) == str:
                    timing = bus_timings[0]
                elif int(bus_timings[0]) > 1:
                    timing = '{}mins'.format(bus_timings[0])
                else:
                    timing = 'Arriving'
                bus_message += '  -{}{}{}\n'.format(timing,
                                                    bus_timings[1].replace('SEA', '🟢').replace('SDA', '🟡').replace(
                                                        'LSD', '🔴'), bus_timings[2].replace('WAB', '♿'))
            else:
                # Bus Number
                bus_message += 'Bus /{}\n'.format(bus_timings)
        bus_message += '\n'
    bus_message += '🟢: Seats Available\n🟡: Standing Available\n🔴: Limited Seating\n♿: Wheel-chair Accessible\n\n' \
                   '<b>Format:</b> Detailed\n<b>Updated:</b> {}'.format(str(datetime.utcnow() + timedelta(hours=8))
                                                                        .rsplit(':', 1)[0])
    keyboard = [
        [InlineKeyboardButton('Refresh', callback_data='callback_refresh'),
         InlineKeyboardButton('General Format', callback_data='callback_format')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    return bus_message, reply_markup, bus_stop_name, bus_stop_code


def short_bus_timing_message(bus_stop_code):
    """
    Create general bus timing message for user in Telegram
    :param bus_stop_code: Bus Stop Code of a bus stop
    :returns: Bus Message, reply_markup, Bus Stop Name, Bus Stop Code
    """
    bus_timings, bus_stop_name, bus_stop_code = get_bus_timing(bus_stop_code)

    bus_message = '<b>Bus Stop: </b>{}\n<b>Bus Stop Code: </b>/{}\n\n'.format(bus_stop_name, bus_stop_code)
    bus_timings.sort(key=lambda x: x[1])

    for bus in bus_timings:
        # Bus Number
        bus_message += 'Bus /{}\n'.format(bus[0])
        if type(bus[1][0]) == str:
            timing = bus[1][0]
        elif int(bus[1][0]) > 1:
            timing = '{}mins'.format(bus[1][0])
        else:
            timing = 'Arriving'
        bus_message += '  -{}{}{}\n\n'.format(timing, bus[1][1].replace('SEA', '🟢').replace('SDA', '🟡').
                                              replace('SEA', '🔴'), bus[1][2].replace('WAB', '♿'))

    bus_message += '🟢: Seats Available\n🟡: Standing Available\n🔴: Limited Seating\n♿: Wheel-chair Accessible\n\n' \
                   '<b>Format:</b> General\n<b>Updated:</b> {}'.format(str(datetime.utcnow() + timedelta(hours=8))
                                                                       .rsplit(':', 1)[0])
    keyboard = [
        [InlineKeyboardButton('Refresh', callback_data='callback_refresh'),
         InlineKeyboardButton('Detailed Format', callback_data='callback_format')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    return bus_message, reply_markup, bus_stop_name, bus_stop_code


def scheduled_bus_timing_format(bus_stop_code, bus_selected_list):
    bus_timings, bus_stop_name, bus_stop_code = get_bus_timing(bus_stop_code)

    bus_message = '<b><u>This is a Scheduled Message</u></b>\n' \
                  '<b>Bus Stop: </b>{}\n<b>Bus Stop Code: </b>/{}\n\n'.format(bus_stop_name, bus_stop_code)

    bus_timings.sort(key=lambda x: x[1])
    for bus in bus_timings:
        # Bus Number
        # To make sure bus is inside the selected list or nothing is being selected(default option-ALL BUS)
        if bus_selected_list == [] or bus[0] in bus_selected_list:
            bus_message += 'Bus /{}\n'.format(bus[0])
            if type(bus[1][0]) == str:
                timing = bus[1][0]
            elif int(bus[1][0]) > 1:
                timing = '{}mins'.format(bus[1][0])
            else:
                timing = 'Arriving'
            bus_message += '  -{}{}{}\n\n'.format(timing, bus[1][1].replace('SEA', '🟢').replace('SDA', '🟡').
                                                  replace('SEA', '🔴'), bus[1][2].replace('WAB', '♿'))

    bus_message += '🟢: Seats Available\n🟡: Standing Available\n🔴: Limited Seating\n♿: Wheel-chair Accessible\n\n' \
                   '<b>Format:</b> General\n<b>Updated:</b> {}'.format(str(datetime.utcnow() + timedelta(hours=8))
                                                                       .rsplit(':', 1)[0])
    keyboard = [
        [InlineKeyboardButton('Refresh', callback_data='callback_refresh'),
         InlineKeyboardButton('Detailed Format', callback_data='callback_format')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    return bus_message, reply_markup, bus_stop_name, bus_stop_code


def get_mrt_alerts():
    url = 'http://datamall2.mytransport.sg/ltaodataservice/TrainServiceAlerts'
    headers = {'AccountKey': LTA_TOKEN_KEY}
    response = requests.get(url, headers=headers).json()

    mrt_service = response['value']
    status = mrt_service['Status']
    # affected_segments and messages will be [] if there is no alert
    affected_segments = mrt_service['AffectedSegments']
    messages = mrt_service['Message']
    if status == 1 and affected_segments == [] and messages == []:
        return 'All Train Services Working Normally 👍'

    if affected_segments:
        affected_segments_msg = '<b>Train Disruption 😫:</b>\n'
        for affected_segment in affected_segments:
            mrt_line = affected_segment['Line']
            direction = affected_segment['Direction']
            stations = affected_segment['Stations']
            public_bus = affected_segment['FreePublicBus']
            mrt_shuttle = affected_segment['FreeMRTShuttle']
            mrt_shuttle_dirn = affected_segment['MRTShuttleDirection']
            affected_segments_msg += mrt_alert_msg(mrt_line, direction, stations, public_bus,
                                                   mrt_shuttle, mrt_shuttle_dirn)
        return affected_segments_msg

    if messages:
        latest_update = '<b>Latest Updates:</b>\n'
        for message in messages:
            # New message will always be index 0
            content = message['Content'].split(':')
            # created_date = message['CreatedDate']
            latest_update += '<b>{}:</b>{}\n\n'.format(content[0], content[1])
        return latest_update
