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

# first_run = False

amzn_ps5_url = "https://www.amazon.com/PlayStation-5-Console/dp/B08FC5L3RG"
test_url = "https://www.amazon.com/Nintendo-Switch-Steering-Controller-TalkWorks-Accessories/dp/B07R679BGS/"
test_url2 = "https://www.amazon.com/DualSense-Wireless-Controller-PlayStation-5/dp/B08FC6C75Y/"
# Test_url is to test application behavior when an item is in stock

curr_dir = Path(__file__).parent
chromedriver_file_path = (curr_dir / "./driver/chromedriver").resolve()
driver = webdriver.Chrome(chromedriver_file_path)

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
    # lowest_prices = soup.find_all('span', {"class": "a-size-base a-color-price"})
    lowest_prices_div = soup.find('div', {"id": "olp_feature_div"})
    lowest_prices = lowest_prices_div.find_all('span', {"class": "a-size-base a-color-price"})
    lowest_price = parse_lowest_price(lowest_prices)

    in_stock = not bool(len(out_of_stock_div_res))
    available_to_buy = bool(len(buy_now_div_res))

    return in_stock, available_to_buy, curr_time, add_button_input, buy_button_input, lowest_price


def report_availability(url=amzn_ps5_url):
    availability = check_availability(url)

    add_to_cart_exists = len(availability[3]) > 0
    buy_now_exists = len(availability[4]) > 0
    lowest_price = availability[5]
    # print(availability)
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


def get_last_availability():
    return  {'time': str(last_time_rec),
            'in_stock': str(in_stock),
            'available_to_buy': str(available_to_buy)}


if __name__ == "__main__":
    report_availability()


# i = 0
# while True and i < 10:
#     time.sleep(10)
#     i += 1
