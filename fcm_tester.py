import requests
import json
import datetime
import random


serverToken = 'Your API key'
deviceToken = 'Your device token'
mobile_device_token = 'Your device token'

low_alert_chann = 'persist'
high_alert_chann = 'alert'
mid_alert_chann = "msgs"

def send_low_priority_message_to_fcm():

    headers = {
        'Content-Type': 'application/json',
        'Authorization': 'key=' + serverToken,
    }

    body = {
        'notification': {'title': 'Sending push from python script',
                         'body': ('Low priority message test.' + str(datetime.datetime.now().replace(microsecond=0))),
                         'android_channel_id': low_alert_chann,
                         'click_action': 'https://www.amazon.com/PlayStation-5-Console/dp/B08FC5L3RG/',
                         },
        'collapse_key': 'collapse',
        'priority': 'normal',
        'to':
            mobile_device_token,
        #   'data': dataPayLoad,

    }
    response = requests.post("https://fcm.googleapis.com/fcm/send", headers=headers, data=json.dumps(body))
    print(response.status_code)
    print(response.json())


def send_mid_priority_message_to_fcm():

    headers = {
        'Content-Type': 'application/json',
        'Authorization': 'key=' + serverToken,
    }

    body = {
        'notification': {'title': 'PS5 in stock from 3rd party.',
                         'body': f"{str(last_time_rec)} - In Stock: {in_stock} - Can Buy: {available_to_buy}",
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


def send_high_priority_message_to_fcm():

    headers = {
        'Content-Type': 'application/json',
        'Authorization': 'key=' + serverToken,
    }

    body = {
        'notification': {'title': 'Sending push from python script',
                         'body': ('High priority message test: ' + str(datetime.datetime.now().replace(microsecond=0))),
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
    print(response.json())


def send_test_message_to_fcm():

    headers = {
        'Content-Type': 'application/json',
        'Authorization': 'key=' + serverToken,
    }

    body = {
        'notification': {'title': 'Sending push from python script',
                         'body': ('Low priority message test.' + str(datetime.datetime.now().replace(microsecond=0))),
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
    print(response.json())


# send_low_priority_message_to_fcm()
# send_high_priority_message_to_fcm()
send_test_message_to_fcm()
# for _ in range(10):
#     print(random.randint(-3, 3))