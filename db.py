from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func, MetaData
from flask_dance.consumer.storage.sqla import OAuthConsumerMixin
from flask_login import UserMixin

convention = {
    "ix": 'ix_%(column_0_label)s',
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s"
}
# sqldb = SQLAlchemy(metadata=MetaData(naming_convention=convention))
sqldb = SQLAlchemy()

class User(UserMixin, sqldb.Model):
    id = sqldb.Column(sqldb.Integer, primary_key=True)
    username = sqldb.Column(sqldb.String, unique=True)
    songs = sqldb.relationship('UserSong', backref='user')


class UserSong(sqldb.Model):
    id = sqldb.Column(sqldb.Integer, primary_key=True)
    desc = sqldb.Column(sqldb.String(150)) #TODO: catch error if greater than 150 char
    saved = sqldb.Column(sqldb.Boolean)
    date = sqldb.Column(sqldb.String)
    period = sqldb.Column(sqldb.String(50))
    year = sqldb.Column(sqldb.Integer)
    song_id = sqldb.Column(sqldb.Integer, sqldb.ForeignKey('song.id'))
    user_id = sqldb.Column(sqldb.Integer, sqldb.ForeignKey('user.id'))


class Song(sqldb.Model):
    id = sqldb.Column(sqldb.Integer, primary_key=True)
    spotify_id = sqldb.Column(sqldb.String)
    name = sqldb.Column(sqldb.String)
    artist = sqldb.Column(sqldb.String)
    plays = sqldb.relationship('UserSong', backref='song')


class OAuth(OAuthConsumerMixin, sqldb.Model):
    user_id = sqldb.Column(sqldb.Integer, sqldb.ForeignKey(User.id))
    user = sqldb.relationship(User)


class Database:
    """
    Class to access database, read and write
    """
    def __init__(self, user):
        self.current_user = user

    def get_saved_songs(self):
        """
        used in /browse
        Returns:

        """
        songs = sqldb.session.query(UserSong.period, UserSong.year, Song.name, Song.artist, Song.spotify_id, UserSong.desc).join(Song, UserSong.song_id == Song.id)\
            .with_parent(self.current_user).filter(UserSong.saved==True).order_by(UserSong.date.desc()).distinct().all()
        # TODO: double check that ordering by date is ok
        resp = []
        prevYear = -1
        years = -1
        # process into 2D array in order grouped by year TODO: is there a better way to do this? via sql?
        for song in songs:
            year = song[1]
            if year != prevYear:
                resp.append([song])
                years += 1
                prevYear = year
            else:
                resp[years].append(song)

        return resp

    def get_period_songs(self, target_period, target_year):
        """
        used in /travel
        Args:
            target_period:

        Returns:

        """
        # TODO: requires UserSong to be queried first; is there a way to make it not so?
        songs = sqldb.session.query(func.count(UserSong.saved), Song.name, Song.artist, func.count(Song.spotify_id), Song.spotify_id).join(Song, UserSong.song_id == Song.id)\
            .with_parent(self.current_user).filter(UserSong.period==target_period, UserSong.year==target_year).group_by(Song.spotify_id)\
            .having(func.count(Song.spotify_id) > 1).order_by(func.count(UserSong.saved).desc(), func.count(Song.spotify_id).desc()).all()

        return songs

    def add_song(self, name, artist, desc, date, song_id, period, year, saved=None):
        """
        Add played song to db. Checks if song exists in db, and if not, adds
        Args:
            saved:
            name:
            artist:
            desc:
            date:
            song_id:
            period:

        Returns:

        """
        song = sqldb.session.query(Song).filter_by(spotify_id=song_id).first()
        if song is None:
            song = Song(name=name, artist=artist, spotify_id=song_id)
            sqldb.session.add(song)
            sqldb.session.commit()

        songRecord = UserSong(desc=desc, user=self.current_user, date=date, period=period, year=year, saved=saved)
        song.plays.append(songRecord)
        sqldb.session.add(songRecord)
        sqldb.session.commit()

    def get_most_recent(self):
        """
        Returns the date of the most recent song the user has played
        Returns:

        """
        recent = sqldb.session.query(UserSong).with_parent(self.current_user).order_by(UserSong.date.desc()).first().date
        return recent

    def save_song(self, sid):
        mark = sqldb.session.query(UserSong).join(Song, Song.id==UserSong.song_id).with_parent(self.current_user).\
            filter(Song.spotify_id==sid).first()
        mark.saved = True if mark.saved is None else None
        sqldb.session.commit()

    @staticmethod
    def reset_saved(current_user=None):
        """
        Set all saved values to None for a current user if provided, or for all if not provided
        Args:
            self:
            current_user:

        Returns:

        """
        if current_user:
            sqldb.session.query(UserSong).with_parent(current_user).filter(UserSong.saved is not None).update({"saved": None})
        else:
            sqldb.session.query(UserSong).filter(UserSong.saved is not None).update({"saved": None})
        sqldb.session.commit()