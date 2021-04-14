import datetime
from apscheduler.events import EVENT_JOB_ERROR
from bs4 import BeautifulSoup
from apscheduler.schedulers.blocking import BlockingScheduler
import threading
import time
import requests
import json
from proxy_scraper import ProxyScraper, headers
import keys

time_format = '%I:%M:%S %p'

serverToken = keys.firebase_api_key
deviceToken = keys.virtual_device_token
mobile_device_token = keys.mobile_device_token

low_alert_chann = 'persist'
mid_alert_chann = "msgs"
high_alert_chann = 'alert'

scheduler = BlockingScheduler()
exceptions_caught = 0

####### Proxy variables ###############
proxy_collector = ProxyScraper()
proxy_stack = []
proxy_stack_secondary = []
last_stack_code = 0

bad_proxies = set()
# tuples of form (ip, site)
last_used_proxy = []


def start_scheduler():
    # schedule_jobs()
    scheduler.add_job(schedule_jobs, 'cron', hour=5, minute=57, second=50)

    # Job for testing
    # scheduler.add_job(schedule_jobs, 'cron', hour=18, minute=14, second=25)

    print("Starting scheduler.")
    scheduler.add_listener(catch_scheduler_exception, EVENT_JOB_ERROR)
    scheduler.start()


def catch_scheduler_exception(event):
    global exceptions_caught
    exceptions_caught += 1
    print("!!! Scheduler caught an exception !!!")

    if exceptions_caught > 5:
        print("!!! Scheduler shutting down due to exceptions !!!")
        shutdown_stock_chkr()


def report_availability(url=None):
    url = "https://www.antonline.com/Sony/Playstation_5"
    thread = threading.Thread(target=_report_availability_thread, args=(url,))
    thread.start()


def _report_availability_thread(url):
    start_time = datetime.datetime.now().replace(microsecond=0)
    print(f"New job: {start_time.strftime(time_format)}")
    result = _rotate_proxies_and_check_results(url)

    if result is None:
        print(f"  -- CURRENT TIME: {datetime.datetime.now().replace(microsecond=0).strftime(time_format)} !!!!")
        print(f"  !! ALL ATTEMPTS EXHAUSTED; JOB FAILED - BEGAN AT: {start_time.strftime(time_format)}!!", end="\n\n")
        return

    curr_time, price, in_stock = result

    for item in result:
        if item is True:
            thread = threading.Thread(target=send_high_priority_message_to_fcm, args=(price, curr_time,))
            thread.start()

    if in_stock is False:
        print("PS5 was not in stock.")
    elif in_stock is None:
        print("!!!! SOME ERROR CHECKING IF STOCK EXISTS !!!!")
    elif in_stock is True:
        print("PS5 IS IN STOCK AT ANTONLINE!!!!!!!!!!")
    if price:
        print(f"Last price recorded: ${price}")
    print(f"Checked at: {curr_time}", end="\n\n")


def update_proxy_stack():
    global last_stack_code
    global proxy_stack_secondary
    global proxy_stack
    proxy_stack_secondary.clear()
    proxy_collector.refresh_proxies()
    time.sleep(4)

    proxy_stack, proxy_stack_secondary, last_stack_code = proxy_collector.get_proxy_stack(proxy_stack, bad_proxies)


def _rotate_proxies_and_check_results(url):
    if len(proxy_stack) == 0:
        update_proxy_stack()
    i = 0
    while proxy_stack:
        proxy = proxy_stack.pop()
        if proxy in bad_proxies:
            continue
        print(f"  -Trying proxy: {proxy}")
        i += 1
        result = scrape_antonline(proxy, url)
        if result is None:
            bad_proxies.add(proxy)
            continue

        proxy_stack.append(proxy)
        last_used_proxy.append((proxy, 'free-proxy-list'))
        return result

    print("\n  -TRYING SECONDARY PROXIES")
    while proxy_stack_secondary:
        proxy = proxy_stack_secondary.pop()
        if proxy in bad_proxies:
            continue
        print(f"  -Trying proxy: {proxy}")
        result = scrape_antonline(proxy, url)
        if result is None:
            bad_proxies.add(proxy)
            continue

        proxy_stack_secondary.append(proxy)
        last_used_proxy.append((proxy, 'proxyscrape'))
        return result

    if i == 0:
        print("  -- THERE WERE NO GOOD PROXIES FOR THE REQUEST.")
    return None


def scrape_antonline(proxy, url="https://www.antonline.com/Sony/Playstation_5"):
    try:
        # Parse using stored html
        # soup = BeautifulSoup(open("antonline_soup.html"), 'html.parser')

        response = requests.get(url, headers=headers,
                                proxies={'http': ('http://' + proxy), 'https': ('https://' + proxy)},
                                timeout=(12.3, 12.3))
        soup = BeautifulSoup(response.text, 'html.parser')
        curr_time = datetime.datetime.now().replace(microsecond=0)

        page_row_divs = soup.find_all('div', {"class": "page_grid_row"})

        results = _parse_antonline_soup_object(page_row_divs)

        if len(results) == 0:
            print("   !!!!!! NO RESULTS FROM PARSED HTML !!!!!!!")
            return
        if True in results:
            return curr_time, results[0], True
        return curr_time, results[0], results[1]

    except Exception as e:
        print("  -Some Exception during scrape/parse!")
        return


def _parse_antonline_soup_object(page_row_divs):
    result = []
    query = "PlayStation 5 Console"
    # query = "Marvel's Spider-Man: Miles Morales"
    for div in page_row_divs:
        if div.text.find(query) != -1:
            text = div.text
            # result.append(text)
            dollar_index = text.find("$")
            if dollar_index != -1:
                result.append(text[dollar_index+1:dollar_index+7])
            else:
                result.append("")
            if "Sold Out" in text:
                result.append(False)
            elif "Add to Cart" in text:
                result.append(True)
                return result
            else:
                result.append(None)

    return result


def send_high_priority_message_to_fcm(price=None, time = None):
    formatted_time = time.strftime(time_format)
    message = f"Checked at: {formatted_time}. Price was: ${price}"
    heading = 'ANTONLINE PS5 AVAILABLE NOW!!!'


    headers = {
        'Content-Type': 'application/json',
        'Authorization': 'key=' + serverToken,
    }

    body = {
        'notification': {'title': heading,
                         'body': message,
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


def schedule_jobs():
    print("Starting scrape jobs.")
    # # scheduler.add_job(schedule_proxy_update_jobs, 'interval', seconds=60)
    # scheduler.add_job(report_availability) #, 'interval', seconds=120)
    # return
    scheduler.add_job(report_availability, 'interval', id='101', seconds=80)

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

    scheduler.add_job(clear_bad_proxies, 'cron', hour='*', minute=14, second=45)
    scheduler.add_job(clear_bad_proxies, 'cron', hour='*', minute=51, second=45)
    scheduler.add_job(clear_bad_proxies, 'cron', hour='*', minute=4, second=40)
    scheduler.add_job(clear_bad_proxies, 'cron', hour='*', minute=34, second=40)


def schedule_proxy_update_jobs():
    thread = threading.Thread(target=update_proxy_stack)
    thread.start()


def clear_bad_proxies():
    print("-- Resetting bad proxies...")
    bad_proxies.clear()


def shutdown_stock_chkr():
    scheduler.shutdown()


if __name__ == "__main__":
    update_proxy_stack()
    start_scheduler()

