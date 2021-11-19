from constants import SECONDS_TO_MILLISECONDS_CONVERSION
from db import *
import datetime


def update_time_elapsed():
    with db.app.app_context():
        db.session.query(Plant).update({
            Plant.time_elapsed: SECONDS_TO_MILLISECONDS_CONVERSION *
            (datetime.datetime.now() - Plant.start_time).total_seconds()
        })

        db.session.commit()
