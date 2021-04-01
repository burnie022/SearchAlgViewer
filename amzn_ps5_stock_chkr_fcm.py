import datetime
from apscheduler.events import EVENT_JOB_ERROR
from selenium import webdriver
from bs4 import BeautifulSoup
from pathlib import Path
import logging
# from flask import Flask
from apscheduler.schedulers.background import BackgroundScheduler
import socket
import threading
import time
import requests
import json
import random


in_stock = False
available_to_buy = False
last_time_rec = datetime.datetime.now().replace(microsecond=0)

# refresh_time_seconds = 120 #90 #50 #45
# message_update_interval = 3 #12 #15 #20
# third_party_stock_interval = 10
first_run = False
k = 0
# third_int = 0
time_format = '%I:%M:%S %p'

serverToken = 'Your API key'
deviceToken = 'Your device token'
mobile_device_token = 'Your device token'


low_alert_chann = 'persist'
mid_alert_chann = "msgs"
high_alert_chann = 'alert'

amzn_ps5_url = "https://www.amazon.com/PlayStation-5-Console/dp/B08FC5L3RG"
test_url = "https://www.amazon.com/Nintendo-Switch-Steering-Controller-TalkWorks-Accessories/dp/B07R679BGS/"
# Test_url is to test application behavior when an item is in stock

curr_dir = Path(__file__).parent
chromedriver_file_path = (curr_dir / "./driver/chromedriver").resolve()
driver = webdriver.Chrome(chromedriver_file_path)

scheduler = BackgroundScheduler(daemon=True)
exceptions_caught = 0

logging_enabled = False
logging.basicConfig(filename='ps5checklog.log', filemode='a', format='%(message)s', level=logging.INFO) #encoding='utf-8',
logging.getLogger('apscheduler.executors.default').setLevel(logging.ERROR)
# logging.getLogger('apscheduler.executors.default').propagate = False

PORT = 5049
SERVER = "192.168.29.106"
server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.bind((SERVER, PORT))


def start_scheduler():
    schedule_jobs(scheduler)
    # scheduler.add_job(report_availability, 'interval', seconds=(refresh_time_seconds))
    #
    # four_secs = datetime.datetime.now() + datetime.timedelta(seconds=4)
    # for job in scheduler.get_jobs():
    #     job.modify(next_run_time=four_secs)

    # A single job to run now
    scheduler.add_job(report_availability)
    scheduler.add_listener(catch_scheduler_exception, EVENT_JOB_ERROR)
    scheduler.start()
    logging.info(f"Date/Time         - In Stock - Can Buy")


#TODO: catch and print the exception
def catch_scheduler_exception(event):
    global exceptions_caught
    exceptions_caught += 1

    thread = threading.Thread(target=send_exception_message_to_fcm)
    thread.start()

    if exceptions_caught > 5:
        thread = threading.Thread(target=send_end_scheduler_message_to_fcm)
        thread.start()
        shutdown_stock_chkr()
        

def parse_lowest_price(price_list):
    if not price_list or len(price_list) == 0:
        print("No price results")
        return None
    price = price_list[0].text
    # print(f"Lowest price: {price}")
    if price.startswith("$"):
        try:
            price = float(price[1:])
            return price
        except:
            print("exception: String to float")
            return None
    print("Low price string did not begin with $")
    return None


def check_availability(url=amzn_ps5_url):
    curr_time = datetime.datetime.now().replace(microsecond=0)
    driver.get(url)

    soup = BeautifulSoup(driver.page_source, 'html.parser')

    out_of_stock_div_res = soup.find_all('div', {"id": "outOfStock"})
    buy_now_div_res = soup.find_all('div', {"id": "buyNow"})
    add_button_input = soup.find_all('input', {'id': "add-to-cart-button"})
    buy_button_input = soup.find_all('input', {'id': "buy-now-button"})
    lowest_prices_div = soup.find('div', {"id": "olp_feature_div"})
    lowest_prices = lowest_prices_div.find_all('span', {"class": "a-size-base a-color-price"})
    lowest_price = parse_lowest_price(lowest_prices)

    in_stock = not bool(len(out_of_stock_div_res))
    available_to_buy = bool(len(buy_now_div_res))

    return in_stock, available_to_buy, curr_time, add_button_input, buy_button_input, lowest_price


def report_availability(url=amzn_ps5_url):
    time.sleep(random.randint(0, 15))
    availability = check_availability(url)

    add_to_cart_exists = len(availability[3]) > 0
    buy_now_exists = len(availability[4]) > 0
    lowest_price = availability[5]

    if add_to_cart_exists:
        print("Add to cart exists.")
    if buy_now_exists:
        print("Buy button exists.")
    if lowest_price:
        print(f"Lowest available price: {lowest_price}")
    print(f"PS5 in stock: {availability[0]}")
    print(f"Available to buy: {availability[1]}")
    print(f"Checked at: {availability[2]}", end="\n\n")

    global in_stock
    if availability[0] != in_stock:
        in_stock = availability[0]
    global available_to_buy
    if availability[1] != available_to_buy:
        available_to_buy = availability[1]
    global last_time_rec
    last_time_rec = availability[2]

    logging.info(f"{str(availability[2])} - {availability[0]} - {availability[1]}")

    global k
    if k == 0:
        thread = threading.Thread(target=send_low_priority_message_to_fcm, args=(lowest_price,))
        thread.start()

    if available_to_buy or add_to_cart_exists or buy_now_exists:
        thread = threading.Thread(target=send_high_priority_message_to_fcm, args=(lowest_price, False,))
        thread.start()
    elif lowest_price and (400 < lowest_price < 600):
        thread = threading.Thread(target=send_mid_priority_message_to_fcm, args=(lowest_price, True,))
        thread.start()

    # k += 1
    # if k >= message_update_interval:
    #     k = 0


def get_last_availability():
    return  {'time': str(last_time_rec),
            'in_stock': str(in_stock),
            'available_to_buy': str(available_to_buy)}


def send_low_priority_message_to_fcm(price=None):
    price_message = f" - Lowest price: ${price}" if price is not None else ""
    formatted_time = last_time_rec.strftime(time_format)
    heading = 'Stock Update.'

    headers = {
        'Content-Type': 'application/json',
        'Authorization': 'key=' + serverToken,
    }

    body = {
        'notification': {'title': heading,
                         'body': f"{str(formatted_time)}{price_message} - Can Buy: {available_to_buy}",
                         'android_channel_id': low_alert_chann,
                         'click_action': 'https://www.amazon.com/PlayStation-5-Console/dp/B08FC5L3RG/',
                         'tag': 'collapse',
                         },
        'collapse_key': 'collapse',
        'priority': 'normal',
        'to':
            mobile_device_token,
        #   'data': dataPayLoad,

    }
    response = requests.post("https://fcm.googleapis.com/fcm/send", headers=headers, data=json.dumps(body))
    print(response.status_code)
    print(response.json(), end="\n\n")


def send_mid_priority_message_to_fcm(price=None, due_to_price=False):
    price_message = f" - Lowest price: ${price}" if price is not None else ""
    heading = 'Lower Priced PS5 available' if due_to_price else 'PS5 AVAILABLE NOW!!!! BUT BUY BUY!!!'
    formatted_time = last_time_rec.strftime(time_format)

    headers = {
        'Content-Type': 'application/json',
        'Authorization': 'key=' + serverToken,
    }

    body = {
        'notification': {'title': heading,
                         'body': f"{str(formatted_time)}{price_message} - Can Buy: {available_to_buy}",
                         'android_channel_id': mid_alert_chann,
                         'click_action': 'https://www.amazon.com/PlayStation-5-Console/dp/B08FC5L3RG/',
                         },
        'priority': 'high',
        'to':
            mobile_device_token,
        #   'data': dataPayLoad,
    }
    response = requests.post("https://fcm.googleapis.com/fcm/send", headers=headers, data=json.dumps(body))
    print(response.status_code)
    print(response.json(), end="\n\n")


def send_high_priority_message_to_fcm(price=None, due_to_price=False):
    price_message = f" - Lowest price: ${price}" if price is not None else ""
    heading = 'Lower Priced PS5 available' if due_to_price else 'PS5 AVAILABLE NOW!!!! BUT BUY BUY!!!'
    formatted_time = last_time_rec.strftime(time_format)

    headers = {
        'Content-Type': 'application/json',
        'Authorization': 'key=' + serverToken,
    }

    body = {
        'notification': {'title': heading,
                         'body': f"{str(formatted_time)}{price_message} - Can Buy: {available_to_buy}",
                         'android_channel_id': high_alert_chann,
                         'click_action': 'https://www.amazon.com/PlayStation-5-Console/dp/B08FC5L3RG/',
                         },
        'priority': 'high',
        'to':
            mobile_device_token,
        #   'data': dataPayLoad,
    }
    response = requests.post("https://fcm.googleapis.com/fcm/send", headers=headers, data=json.dumps(body))
    print(response.status_code)
    print(response.json(), end="\n\n")


def send_exception_message_to_fcm():
    formatted_time = last_time_rec.strftime(time_format)

    headers = {
        'Content-Type': 'application/json',
        'Authorization': 'key=' + serverToken,
    }

    body = {
        'notification': {'title': 'Caught an Exception',
                         'body': f"Check at {formatted_time} returned an exception.",
                         'android_channel_id': low_alert_chann,
                         'click_action': 'https://www.amazon.com/PlayStation-5-Console/dp/B08FC5L3RG/',
                         },
        'collapse_key': 'collapse',
        'priority': 'normal',
        'to':
            mobile_device_token,
    }
    response = requests.post("https://fcm.googleapis.com/fcm/send", headers=headers, data=json.dumps(body))
    print(response.status_code)
    print(response.json(), end="\n\n")


def send_end_scheduler_message_to_fcm():
    formatted_time = last_time_rec.strftime(time_format)

    headers = {
        'Content-Type': 'application/json',
        'Authorization': 'key=' + serverToken,
    }

    body = {
        'notification': {'title': 'Stopping Stock Checker',
                         'body': f"Stopping at {formatted_time} due to exceptions.",
                         'android_channel_id': mid_alert_chann,
                         'click_action': 'https://www.amazon.com/PlayStation-5-Console/dp/B08FC5L3RG/',
                         },
        'collapse_key': 'collapse',
        'priority': 'normal',
        'to':
            mobile_device_token,
    }
    response = requests.post("https://fcm.googleapis.com/fcm/send", headers=headers, data=json.dumps(body))
    print(response.status_code)
    print(response.json(), end="\n\n")


def before_time(hour_min_sec="08:00:00"):
    now = datetime.datetime.now()

    my_datetime = datetime.datetime.strptime(hour_min_sec, "%H:%M:%S")
    my_datetime = now.replace(hour=my_datetime.time().hour, minute=my_datetime.time().minute,
                                    second=my_datetime.time().second, microsecond=0)

    return now < my_datetime


def schedule_jobs(scheduler):
    # jobs = [
    #     # id   hr  min sec jitter
    #     ('00', '*', 0, 10, 40),
    #     ('01', '*', 1, 10, 15),
    #     ('02', '*', 2, 10, 15),
    #     ('03', '*', 3, 10, 25),
    #     ('04', '*', 4, 10, 25),
    #     ('06', '*', 6, 10, 55),
    #     ('08', '*', 8, 10, 45),
    #     ('10', '*', 10, 10, 30),
    #     ('15', '*', 15, 10, 45),
    #     ('21', '*', 21, 10, 60),
    #     ('26', '*', 26, 10, 60),
    #     ('30', '*', 30, 10, 30),
    #     ('37', '*', 37, 10, 45),
    #     ('45', '*', 45, 10, 60),
    #     ('53', '*', 53, 10, 60),
    # ]

    # Hopefully these checks won't get CAPTCHA
    jobs = [
        # id   hr  min sec jitter
        ('00',  0, 1, 10, 180),
        ('01',  1, 1, 10, 120),
        ('03',  3, 1, 10, 120),
        ('06',  6, 1, 10, 120),
        ('07',  7, 1, 15, 90),
        ('08',  8, 1, 10, 180),
        ('09',  9, 0, 10, 90),
        ('12', 12, 0, 10, 180),
        ('13', 13, 0, 10, 180),
        ('13', 13, 0, 10, 180)
    ]

    for i, hr, m, s, j in jobs:
        scheduler.add_job(report_availability, 'cron', id=i, hour=hr, minute=m, second=s, jitter=j)

    # scheduler.add_job(pause_jobs, 'cron', id='000', hour=22, minute=18, second=0)
    # scheduler.add_job(resume_jobs, 'cron', id='001', hour=6, minute=58, second=55)


# job_ids_pausable = ('02', '04', '08', '10', '21', '26', '37', '45', '53')
job_ids_pausable = ('02', '04', '08', '10', '21', '26', '37', '45', '53')


def pause_jobs():
    for job in job_ids_pausable:
        scheduler.pause_job(job)

def resume_jobs():
    for job in job_ids_pausable:
        scheduler.resume_job(job)


def shutdown_stock_chkr():
    scheduler.shutdown()
    server.shutdown(socket.SHUT_RDWR)
    server.close()


def start_local_server():
    print(f"Starting server on port {PORT}")
    server.listen()
    print(f"Server is listening on {SERVER}")
    while True:
        conn, addr = server.accept()
        curr_time = datetime.datetime.now().replace(microsecond=0)

        print(f"- Accepted new connection at: {curr_time}")
        print(f"- Active connections: {threading.activeCount() - 1}")
        conn.close()


if __name__ == "__main__":
    start_scheduler()
    start_local_server()


# i = 0
# while True: # and i < 2:
#     # time.sleep(10)
#     # print(i)
#     i += 1
