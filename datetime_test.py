import datetime


def before_time(hour_min_sec = "08:00:00"):
    now = datetime.datetime.now()

    my_datetime = datetime.datetime.strptime(hour_min_sec, "%H:%M:%S")
    my_datetime = now.replace(hour=my_datetime.time().hour, minute=my_datetime.time().minute,
                                    second=my_datetime.time().second, microsecond=0)

    return now < my_datetime


if before_time("15:49:00"):
    print("yep")
else:
    print("Nope")
