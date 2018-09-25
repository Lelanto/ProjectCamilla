from datetime import date, time, datetime, timedelta
from random import randint
print str(datetime.now()+timedelta(seconds=randint(100, 400))).split(" ")[1].split(".")[0]