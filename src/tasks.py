from db import *

def update_time_elapsed():
    with db.app.app_context():
        print(Plant.query.all())
