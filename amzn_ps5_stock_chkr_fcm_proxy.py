import datetime
from apscheduler.events import EVENT_JOB_ERROR
from bs4 import BeautifulSoup
import logging
from apscheduler.schedulers.blocking import BlockingScheduler
import threading
import time
import requests
import json
from proxy_scraper import ProxyScraper, headers
import keys

in_stock = False
available_to_buy = False
last_time_rec = datetime.datetime.now().replace(microsecond=0)

# refresh_time_seconds = 120 #90 #50 #45
# message_update_interval = 3 #12 #15 #20
# third_party_stock_interval = 10
first_run = False
k = 0
time_format = '%I:%M:%S %p'

serverToken = keys.firebase_api_key
deviceToken = keys.virtual_device_token
mobile_device_token = keys.mobile_device_token

low_alert_chann = 'persist'
mid_alert_chann = "msgs"
high_alert_chann = 'alert'

amzn_ps5_url = "https://www.amazon.com/PlayStation-5-Console/dp/B08FC5L3RG"
test_url = "https://www.amazon.com/Nintendo-Switch-Steering-Controller-TalkWorks-Accessories/dp/B07R679BGS/"

scheduler = BlockingScheduler()
exceptions_caught = 0

logging_enabled = False
logging.basicConfig(filename='ps5checklog.log', filemode='a', format='%(message)s',
                    level=logging.INFO)  # encoding='utf-8',
logging.getLogger('apscheduler.executors.default').setLevel(logging.ERROR)

####### Proxy variables ###############
proxy_collector = ProxyScraper()
proxy_stack = []
proxy_stack_secondary = []
last_stack_code = 0

bad_proxies = set()


def start_scheduler():
    schedule_jobs(scheduler)

    scheduler.add_listener(catch_scheduler_exception, EVENT_JOB_ERROR)
    scheduler.start()
    logging.info(f"Date/Time         - In Stock - Can Buy")


# TODO: catch and print the exception
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
    if price.startswith("$"):
        try:
            price = float(price[1:])
            return price
        except:
            print("exception: String to float")
            return None
    print("Low price string did not begin with $")
    return None



def report_availability(url=amzn_ps5_url):
    thread = threading.Thread(target=_report_availability_thread, args=(url,))
    thread.start()


def _report_availability_thread(url=amzn_ps5_url):
    start_time = datetime.datetime.now().replace(microsecond=0)
    print(f"-- New job: {start_time.strftime(time_format)}")
    result = _rotate_proxies_and_check_results(url)

    if result is None:
        send_proxy_fail_message_to_fcm(start_time)
        print(f"\n!!!! CURRENT TIME: {datetime.datetime.now().replace(microsecond=0).strftime(time_format)} !!!!")
        print(f"!!!! FAILED ALL ATTEMPTS TO CONNECT TO AMAZON OR PARSE INFORMATION -- ATTEMPTED AT: {start_time.strftime(time_format)}!!!!", end="\n\n")
        return

    # Check availability: return 2 objects - soup object or None, and boolean that says true if bad proxy

    in_stock_r, available_to_buy_r, curr_time, add_button_input, buy_button_input, lowest_price = result

    add_to_cart_exists = len(add_button_input) > 0
    buy_now_exists = len(buy_button_input) > 0
    lowest_price = lowest_price

    if add_to_cart_exists:
        print("Add to cart exists.")
    if buy_now_exists:
        print("Buy button exists.")
    if lowest_price:
        print(f"Lowest available price: {lowest_price}")
    print(f"PS5 in stock: {in_stock_r}")
    print(f"Available to buy: {available_to_buy_r}")
    print(f"Checked at: {curr_time}", end="\n\n")

    global in_stock
    if in_stock != in_stock_r:
        in_stock = in_stock_r
    global available_to_buy
    if available_to_buy != available_to_buy_r:
        available_to_buy = available_to_buy_r
    global last_time_rec
    last_time_rec = curr_time

    logging.info(f"{str(curr_time)} - {in_stock_r} - {available_to_buy_r}")

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


def update_proxy_stack():
    # proxy_stack.clear()
    global last_stack_code
    global proxy_stack_secondary
    global proxy_stack
    proxy_stack_secondary.clear()
    proxy_collector.refresh_proxies()
    time.sleep(4)

    proxy_stack, proxy_stack_secondary, last_stack_code = proxy_collector.get_proxy_stack(proxy_stack, bad_proxies)
    # proxy_stack.extend(stack_primary)
    # proxy_stack_secondary.extend(stack_secondary)

def _rotate_proxies_and_check_results(url=amzn_ps5_url):
    if len(proxy_stack) == 0:
        update_proxy_stack()
    i = 0
    while proxy_stack:
        proxy = proxy_stack.pop()
        if proxy in bad_proxies:
            continue
        print(f"Trying proxy: {proxy}")
        i += 1
        is_bad, result = _scrape_amazon(proxy, url)
        if is_bad or result is None:
            bad_proxies.add(proxy)
            continue

        proxy_stack.append(proxy)
        return result

    print("\nTRYING SECONDARY PROXIES")
    while proxy_stack_secondary:
        proxy = proxy_stack_secondary.pop()
        print(f"Trying proxy: {proxy}")
        if proxy in bad_proxies:
            continue
        is_bad, result = _scrape_amazon(proxy, url)
        if is_bad or result is None:
            bad_proxies.add(proxy)
            continue

        proxy_stack_secondary.append(proxy)
        return result

    if i == 0:
        print("!!!!!! THERE WERE NO GOOD PROXIES FOR THE REQUEST !!!!!!!")
    return None

#TODO: Limit concurrent threads (maybe by storing ids)
#TODO: Store these in a firebase database. Have them fetched at start, and at interval,
# and stored on firebase at interval as well
#TODO: Print thread start and end notifications, maybe add some color
def _scrape_amazon(proxy, url=amzn_ps5_url):
    try:
        response = requests.get(url, headers=headers,
                                proxies={'http': ('http://' + proxy), 'https': ('https://' + proxy)},
                                timeout=(15.05, 18.05))
        if "To discuss automated access to Amazon data please contact" in response.text:
            print("-----    Page was blocked by Amazon      -----")
            return _bad_request()
        elif response.status_code > 500:
            print("Page %s must have been blocked by Amazon as the status code was %d" % (url, response.status_code))
            return _bad_request()
        else:
            soup = BeautifulSoup(response.text, 'html.parser')
            product_title_div = soup.find('div', {"id": "titleSection"})
            product_title = product_title_div.find_all('span', {"id": "productTitle"})
            if len(product_title) == 0:
                print("!!  PS5 wasn't in the response  !!")
                return _bad_request()

            return False, _parse_ps5_soup_object(soup)

    except Exception as e:
        if e == requests.exceptions.RequestException:
            print("!!! Proxy request timed out. Skipping.")
        else:
            print("!!! Skipping. Some Exception while retrieving with proxy or when parsing !!!!")
        return _bad_request()


def _bad_request():
    return True, None


def _parse_ps5_soup_object(soup):
    curr_time = datetime.datetime.now().replace(microsecond=0)

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


def get_last_availability():
    return {'time': str(last_time_rec),
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
    now = datetime.datetime.now().replace(microsecond=0)
    formatted_time = now.strftime(time_format)

    headers = {
        'Content-Type': 'application/json',
        'Authorization': 'key=' + serverToken,
    }

    body = {
        'notification': {'title': 'Scheduler caught an Exception',
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


def send_proxy_fail_message_to_fcm(fail_time):
    now = datetime.datetime.now().replace(microsecond=0)
    formatted_time = fail_time.strftime(time_format)
    title_message = f"Failed to parse. Current time: {now.strftime(time_format)}"

    headers = {
        'Content-Type': 'application/json',
        'Authorization': 'key=' + serverToken,
    }

    body = {
        'notification': {'title': title_message,
                         'body': f"Proxies failed check scheduled at {formatted_time}.",
                         'android_channel_id': low_alert_chann,
                         'click_action': 'https://www.amazon.com/PlayStation-5-Console/dp/B08FC5L3RG/',
                         'tag': 'failed',
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
    # # scheduler.add_job(schedule_proxy_update_jobs, 'interval', seconds=60)
    # scheduler.add_job(report_availability, 'interval', seconds=90)
    # return

    jobs = [
        # id   hr  min sec jitter
        ('00', '*', 0, 10, 0),
        # ('01', '*', 1, 10, 0),
        ('02', '*', 2, 20, 0),
        # ('03', '*', 3, 10, 0),
        ('03b', '*', 3, 50, 0),
        ('05', '*', 5, 35, 0),
        # ('06', '*', 6, 45, 0),
        ('08', '*', 8, 30, 0),
        ('10', '*', 10, 30, 0),
        ('12', '*', 12, 30, 0),
        ('15', '*', 15, 30, 0),
        ('18', '*', 18, 25, 0),
        ('21', '*', 21, 10, 0),
        ('26', '*', 26, 0, 0),
        ('30', '*', 30, 15, 0),
        ('32', '*', 32, 30, 0),
        ('35', '*', 35, 30, 0),
        ('38', '*', 38, 30, 0),
        ('45', '*', 45, 10, 0),
        ('49', '*', 49, 10, 0),
        ('52', '*', 52, 30, 0),
        ('55', '*', 55, 30, 0),
    ]

    for i, hr, m, s, j in jobs:
        scheduler.add_job(report_availability, 'cron', id=i, hour=hr, minute=m, second=s, jitter=j)

    update_proxy_jobs = [
        # id   hr  min sec jitter
        ('a', '*', 5,  0,  0),
        ('b', '*', 10,  0,  0),
        ('c', '*', 15,  0,  0),
        ('d', '*', 25,  30,  0),
        ('e', '*', 35,  0,  0),
        ('f', '*', 44,  30,  0),
        ('g', '*', 52,  0,  0),
        ('h', '*', 59,  30,  0)
    ]

    for i, hr, m, s, j in update_proxy_jobs:
        scheduler.add_job(schedule_proxy_update_jobs, 'cron', id=i, hour=hr, minute=m, second=s, jitter=j)

    # scheduler.add_job(pause_jobs, 'cron', id='000', hour=22, minute=17, second=0)
    # scheduler.add_job(resume_jobs, 'cron', id='001', hour=6, minute=58, second=55)
    scheduler.add_job(pause_jobs)


def schedule_proxy_update_jobs():
    thread = threading.Thread(target=update_proxy_stack)
    thread.start()


pausable_jobs = ('02', '03b', '10', '12', '18', '26', '32', '38', '49', '55')
def pause_jobs():
    for job in pausable_jobs:
        scheduler.pause_job(job)

def resume_jobs():
    for job in pausable_jobs:
        scheduler.resume_job(job)


def shutdown_stock_chkr():
    scheduler.shutdown()


if __name__ == "__main__":
    update_proxy_stack()
    start_scheduler()

