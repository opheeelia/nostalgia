from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func
from flask_dance.consumer.storage.sqla import OAuthConsumerMixin
from flask_login import UserMixin

sqldb = SQLAlchemy()


class User(UserMixin, sqldb.Model):
    id = sqldb.Column(sqldb.Integer, primary_key=True)
    username = sqldb.Column(sqldb.String, unique=True)
    songs = sqldb.relationship('Song', backref='song_user')


class OAuth(OAuthConsumerMixin, sqldb.Model):
    user_id = sqldb.Column(sqldb.Integer, sqldb.ForeignKey(User.id))
    user = sqldb.relationship(User)


class Song(sqldb.Model):
    id = sqldb.Column(sqldb.Integer, primary_key=True)
    spotify_id = sqldb.Column(sqldb.String)
    date = sqldb.Column(sqldb.String)
    period = sqldb.Column(sqldb.String(50))
    name = sqldb.Column(sqldb.String)
    artist = sqldb.Column(sqldb.String)
    desc = sqldb.Column(sqldb.String(150))
    saved = sqldb.Column(sqldb.Boolean)
    user_id = sqldb.Column(sqldb.Integer, sqldb.ForeignKey('user.id'))


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
        songs = sqldb.session.query(Song.period, Song.name, Song.artist, Song.spotify_id, Song.desc)\
            .with_parent(self.current_user).filter_by(saved=True).order_by(Song.date.desc()).distinct().all()
        return songs

    def get_period_songs(self, target_period):
        """
        used in /travel
        Args:
            target_period:

        Returns:

        """
        songs = sqldb.session.query(Song.name, Song.artist, func.count(Song.spotify_id), Song.spotify_id, func.count(Song.saved))\
            .with_parent(self.current_user).filter_by(period=target_period).group_by(Song.spotify_id)\
            .having(func.count(Song.spotify_id) > 1).order_by(func.count(Song.saved).desc(), func.count(Song.spotify_id).desc()).all()

        return songs

    def add_song(self, *, name, artist, desc, date, song_id, period):
        """
        Add played song to db
        Args:
            name:
            artist:
            desc:
            date:
            song_id:
            period:

        Returns:

        """
        song = Song(name=name, artist=artist, desc=desc, song_user=self.current_user, date=date, spotify_id=song_id,
                       period=period, saved=None)
        sqldb.session.add(song)
        sqldb.session.commit()

    def get_most_recent(self):
        """
        Returns the date of the most recent song the user has played
        Returns:

        """
        recent = sqldb.session.query(Song).with_parent(self.current_user).order_by(Song.date.desc()).first().date
        return recent

    def save_song(self, sid):
        mark = sqldb.session.query(Song).with_parent(self.current_user).filter_by(spotify_id=sid) \
            .order_by(Song.saved.desc()).first()
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
            sqldb.session.query(Song).with_parent(current_user).filter(Song.saved is not None).update({"saved": None})
        else:
            sqldb.session.query(Song).filter(Song.saved is not None).update({"saved": None})
        sqldb.session.commit()