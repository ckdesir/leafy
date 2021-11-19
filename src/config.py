from tasks import update_time_elapsed


class Config(object):
    SQLALCHEMY_DATABASE_URI = 'sqlite:///leafy.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ECHO = False
    # JOBS = [{"id": "update_interval", "func": update_time_elapsed,
    #          "trigger": "interval", "seconds": 50}]

    # JOBS = [{"id": "update_interval", "func": update_time_elapsed,
    #          "trigger": "interval", "minutes": 60}]
