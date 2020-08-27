import sqlite3
# from app import app
from flask_sqlalchemy import SQLAlchemy
from flask_dance.consumer.storage.sqla import OAuthConsumerMixin, SQLAlchemyStorage
from flask_login import UserMixin

db = "main_db"
#
# sqldb = SQLAlchemy(app)
#
#
# class User(UserMixin, sqldb.Model):
#     id = sqldb.Column(sqldb.Integer, primary_key=True)
#     username = sqldb.Column(sqldb.String, unique=True)
#
# class OAuth(OAuthConsumerMixin, sqldb.Model):
#     user_id = sqldb.Column(sqldb.Integer, sqldb.ForeignKey(User.id))
#     user = sqldb.relationship(User)

class Database:
    def __init__(self, user_id):
        self.user_id = user_id

        conn = sqlite3.connect(db)  # connect to that database (will create if it doesn't already exist)
        c = conn.cursor()  # move cursor into database (allows us to execute commands)
        c.execute('CREATE TABLE IF NOT EXISTS main_table (user TEXT, song_id TEXT, song_name TEXT, datetime TEXT, period TEXT);')  # run a CREATE TABLE command
        conn.commit()  # commit commands
        conn.close()  # close connection to database

    def clear_database(self):
        conn = sqlite3.connect(db)
        c = conn.cursor()
        c.execute('DELETE FROM main_table')
        conn.commit()
        conn.close()

    def add_song(self, datetime, name, song_id):
        season = {1: 'Winter',
                  2: 'Winter',
                  3: 'Spring',
                  4: 'Spring',
                  5: 'Spring',
                  6: 'Summer',
                  7: 'Summer',
                  8: 'Summer',
                  9: 'Fall',
                  10: 'Fall',
                  11: 'Fall',
                  12: 'Winter',
                  }

        # parse datetime ex. 2020-08-20T21:43:25.567Z
        year, month, *_ = datetime.split('-')

        # declare period
        period = season[int(month)] + ' ' + year

        conn = sqlite3.connect(db)
        c = conn.cursor()
        c.execute('INSERT INTO main_table (user, song_id, song_name, datetime, period) VALUES (?,?,?,?,?) ',
                  (self.user_id, song_id, name, datetime, period))
        conn.commit()
        conn.close()

    def add_new_songs(self, potential_songs):
        # given a list of songs, add if it occurs before the most recent song in database
        conn = sqlite3.connect(db)
        c = conn.cursor()
        try:
            most_recent = c.execute('SELECT datetime FROM main_table WHERE (user=?) ORDER BY datetime DESC LIMIT 1',
                                    (self.user_id,)).fetchone()[0]
        except TypeError:
            most_recent = "0"

        conn.commit()
        conn.close()

        for date, name, song_id in potential_songs:
            if date <= most_recent:
                break
            self.add_song(date, name, song_id)

    def get_all(self):
        conn = sqlite3.connect(db)
        c = conn.cursor()
        data = c.execute('SELECT * FROM main_table ORDER BY datetime DESC').fetchall()
        conn.commit()
        conn.close()
        return data

    def get_by_period(self, period, max_songs=20):
        if period is None:
            return []
        conn = sqlite3.connect(db)
        c = conn.cursor()
        data = c.execute('SELECT song_id, song_name, COUNT(song_id) FROM main_table WHERE (user=? AND period=?) GROUP BY song_id ORDER BY COUNT(song_id) DESC LIMIT ?', (self.user_id, period, max_songs)).fetchall()
        conn.commit()
        conn.close()
        return data