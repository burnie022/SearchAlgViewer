# import requests
import datetime
from selenium import webdriver
from bs4 import BeautifulSoup
from pathlib import Path
import logging
# from flask import Flask
from apscheduler.schedulers.background import BackgroundScheduler
import socket
import threading
import time


in_stock = False
available_to_buy = False
last_time_rec = datetime.datetime.now().replace(microsecond=0)

# refresh_time_minutes = 2
refresh_time_seconds = 120
first_run = False

amzn_ps5_url = "https://www.amazon.com/PlayStation-5-Console/dp/B08FC5L3RG"
test_url = "https://www.amazon.com/Nintendo-Switch-Steering-Controller-TalkWorks-Accessories/dp/B07R679BGS/"
# Test_url is to test application behavior when an item is in stock

HEADER = 128
PORT = 5050
SERVER = "192.168.29.106"
ADDR = (SERVER, PORT)
FORMAT = "utf-8"
DISCONNECT_MESSAGE = "!DISCONNECT"

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.bind(ADDR)

curr_dir = Path(__file__).parent
chromedriver_file_path = (curr_dir / "./driver/chromedriver").resolve()
driver = webdriver.Chrome(chromedriver_file_path)

scheduler = BackgroundScheduler(daemon=True)

logging_enabled = False
logging.basicConfig(filename='ps5checklog.log', filemode='a', format='%(message)s', level=logging.INFO) #encoding='utf-8',
logging.getLogger('apscheduler.executors.default').setLevel(logging.ERROR)
# logging.getLogger('apscheduler.executors.default').propagate = False

def start_local_server():
    print(f"Starting server on port {PORT}")
    server.listen()
    print(f"Server is listening on {SERVER}")
    while True:
        conn, addr = server.accept()
        curr_time = datetime.datetime.now().replace(microsecond=0)

        print(f"- Accepted new connection at: {curr_time}")
        thread = threading.Thread(target=handle_client, args=(conn, addr))
        thread.start()
        print(f"- Active connections: {threading.activeCount() - 1}")


# def handle_client(conn, addr):
#     connected = True
#     while connected:
#         # msg_length = conn.recv(HEADER).decode(FORMAT)
#         message = conn.recv(HEADER)
#         msg_length = message.decode(FORMAT)
#
#         if msg_length:
#             msg_length = int(msg_length)
#             msg = conn.recv(msg_length).decode(FORMAT)
#             if msg == DISCONNECT_MESSAGE:
#                 connected = False
#             else:
#                 # send_client_message(conn, "Test")
#                 send_availability(conn)
#                 break
#
#
#             print(f"[{addr}] {msg}")
#
#     conn.close()

def handle_client(conn, addr):
    connected = True
    while connected:
        # A string with a single whitespace character is apparently 32 bytes.
        message = conn.recv(32)

        if message:
            # send_availability(conn)
            send_availability_to_dart_client(conn)
            break
            # print(f"[{addr}] {msg}")

    conn.close()
    print("- Message sent. Disconnected.", end="\n\n")


def send_client_message(conn, msg):
    message = msg.encode(FORMAT)
    msg_length = len(message)
    send_length = str(msg_length).encode(FORMAT)
    send_length += b' ' * (HEADER - len(send_length))
    conn.send(send_length)
    conn.send(message)


def send_availability(conn):
    message = str(get_last_availability()).encode(FORMAT)
    msg_length = len(message)
    send_length = str(msg_length).encode(FORMAT)
    send_length += b' ' * (HEADER - len(send_length))
    conn.send(send_length)
    conn.send(message)


def send_availability_to_dart_client(conn):
    # the Flutter/Dart client doesn't need to receive a header specifying message length apparently
    message = str(get_last_availability()).encode(FORMAT)
    conn.send(message)


def start_scheduler():
    scheduler.add_job(report_availability, 'interval', seconds=refresh_time_seconds)
    scheduler.start()

    four_secs = datetime.datetime.now() + datetime.timedelta(seconds=4)
    for job in scheduler.get_jobs():
        job.modify(next_run_time=four_secs)
    logging.info(f"Date/Time         - In Stock - Can Buy")
        

def check_availability(url=amzn_ps5_url):
    curr_time = datetime.datetime.now().replace(microsecond=0)
    driver.get(url)

    soup = BeautifulSoup(driver.page_source, 'html.parser')

    out_of_stock_div_res = soup.find_all('div', {"id": "outOfStock"})
    buy_now_div_res = soup.find_all('div', {"id": "buyNow"})

    in_stock = not bool(len(out_of_stock_div_res))
    available_to_buy = bool(len(buy_now_div_res))

    return in_stock, available_to_buy, curr_time


def report_availability(url=amzn_ps5_url):
    availability = check_availability(url)

    print(availability)
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


def get_last_availability():
    return  {'time': str(last_time_rec),
            'in_stock': str(in_stock),
            'available_to_buy': str(available_to_buy)}


if __name__ == "__main__":
    start_scheduler()
    start_local_server()


# i = 0
# while True and i < 10:
#     time.sleep(10)
#     i += 1
