import os
import requests

ACCOUNT_KEY = os.environ.get('LTA_TOKEN_KEY')


def update_bus_stops():
    """
    Gets all the bus stops from the LTA API and store them in bus_stops.txt
    Each row in bus_stops.txt will have a bus stop code, road name, description, latitude and longitude
    """
    list_bus_stops = list()

    length_json, interval = 500, 1

    while length_json == 500:
        url = "http://datamall2.mytransport.sg/ltaodataservice/BusStops?$skip={}".format(interval * 500)
        headers = {'AccountKey': ACCOUNT_KEY}
        response = requests.get(url, headers=headers).json()

        for bus_stop in response["value"]:
            list_bus_stops.append([bus_stop["BusStopCode"], bus_stop["RoadName"], bus_stop["Description"],
                                  bus_stop["Latitude"], bus_stop["Longitude"]])

        length_json = len(response['value'])
        interval += 1

    with open("bus_stops.txt", "w") as r:
        for bus_stop in list_bus_stops:
            r.write('{} | {} | {} | {} | {}\n'.format(bus_stop[0], bus_stop[1].upper(), bus_stop[2].upper(),
                                                      bus_stop[3], bus_stop[4]))


def get_bus_stop_name():
    """
    Gets all the bus stop names
    :return: List of all the bus stop code and road name
    """
    bus_stop_list = list()
    with open('bus_stops.txt', 'r') as r:
        for bus_stop in r.readlines():
            number_code = bus_stop.split(' | ', 5)[0]
            road_name = bus_stop.split(' | ', 5)[2]
            bus_stop_list.append([number_code, road_name])
    return bus_stop_list


def bus_routes():
    """
    Gets all the bus routes from the LTA API and store them in bus_routes.txt
    Each row in bus_routes.txt will have a bus service number, direction, bus stop code, bus stop name,
    first and last bus timings for weekdays, Saturday and Sunday
    """
    os.remove('bus_routes.txt')
    bus_stop_list = get_bus_stop_name()

    length_json, interval = 500, 1

    while length_json == 500:
        url = "http://datamall2.mytransport.sg/ltaodataservice/BusRoutes?$skip={}".format(interval * 500)
        headers = {'AccountKey': ACCOUNT_KEY}
        response = requests.get(url, headers=headers).json()
        routes = response['value']
        for route in routes:
            for bus_stop in bus_stop_list:
                if route['BusStopCode'] == bus_stop[0]:
                    with open('bus_routes.txt', 'a') as r:
                        r.write('{} | {} | {} | {} | {} | {} | {} '
                                '| {} | {} | {}\n'.format(route['ServiceNo'], route['Direction'], route['BusStopCode'],
                                                          bus_stop[1].upper(), route['WD_FirstBus'],
                                                          route['WD_LastBus'], route['SAT_FirstBus'],
                                                          route['SAT_LastBus'], route['SUN_FirstBus'],
                                                          route['SUN_LastBus']))

        length_json = len(response['value'])
        interval += 1


if __name__ == "__main__":
    bus_routes()
    update_bus_stops()
