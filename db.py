from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func, MetaData
from flask_dance.consumer.storage.sqla import OAuthConsumerMixin
from flask_login import UserMixin
from sqlalchemy.ext.mutable import MutableList

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
    username = sqldb.Column(sqldb.String(100), unique=True)
    recent = sqldb.Column(sqldb.String(60))
    songs = sqldb.relationship('UserSong', backref='user')


class UserSong(sqldb.Model):
    id = sqldb.Column(sqldb.Integer, primary_key=True)
    desc = sqldb.Column(sqldb.String(150)) #TODO: catch error if greater than 150 char
    saved = sqldb.Column(sqldb.Boolean)
    date = sqldb.Column(MutableList.as_mutable(sqldb.ARRAY(sqldb.String(60))))
    plays = sqldb.Column(sqldb.Integer)
    period = sqldb.Column(sqldb.Enum('Spring', 'Summer', 'Fall', 'Winter', name='periodenum'))
    year = sqldb.Column(sqldb.Integer)
    song_id = sqldb.Column(sqldb.Integer, sqldb.ForeignKey('song.id'))
    user_id = sqldb.Column(sqldb.Integer, sqldb.ForeignKey('user.id'))


class Song(sqldb.Model):
    id = sqldb.Column(sqldb.Integer, primary_key=True)
    spotify_id = sqldb.Column(sqldb.String(100))
    name = sqldb.Column(sqldb.String(100))
    artist = sqldb.Column(sqldb.String(100))
    image = sqldb.Column(sqldb.String(300))  # link to image
    preview = sqldb.Column(sqldb.String(300))  # link to preview
    link = sqldb.Column(sqldb.String(300))
    plays = sqldb.relationship('UserSong', backref='song')


class OAuth(OAuthConsumerMixin, sqldb.Model):
    user_id = sqldb.Column(sqldb.Integer, sqldb.ForeignKey(User.id))
    user = sqldb.relationship(User)


class Database:
    """
    Class to access database, read and write
    """
    MIN_PLAYED = 1
    def __init__(self, user):
        self.current_user = user

    def get_saved_songs(self):
        """
        used in /browse
        Returns:

        """
        songs = sqldb.session.query(UserSong.period, UserSong.year, Song.name, Song.artist, UserSong.id, UserSong.desc,
                                    Song.image, Song.link, Song.preview).join(Song, UserSong.song_id == Song.id)\
            .with_parent(self.current_user).filter(UserSong.saved==True).order_by(UserSong.year.desc(), UserSong.period.asc()).distinct().all()

        # todo: order such that period=none is at the top
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
        used in /discover
        Args:
            target_year:
            target_period:

        Returns:

        """
        # TODO: requires UserSong to be queried first; is there a way to make it not so?
        filters = [UserSong.period == target_period, UserSong.year == target_year] if target_period else [
            UserSong.year == target_year] if target_year else []

        songs = sqldb.session.query(UserSong.saved, Song.name, Song.artist, UserSong.plays,
                                    UserSong.id, Song.image, Song.link).join(Song, UserSong.song_id == Song.id)\
            .with_parent(self.current_user).filter(*filters, (UserSong.plays >= Database.MIN_PLAYED) | (UserSong.saved != None))\
            .order_by(UserSong.saved.desc(), UserSong.plays.desc()).all()

        return songs

    def add_song(self, name, artist, desc, date, song_id, year, preview, image, link, plays=1, period=None, saved=None):
        """
        Add played song to db. Checks if song exists in db, and if not, adds. Updates the users most recent song date
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
        # create song obj if doesnt exist
        song = sqldb.session.query(Song).filter_by(spotify_id=song_id).first()
        if song is None:
            song = Song(name=name, artist=artist, preview=preview, image=image, link=link, spotify_id=song_id)
            sqldb.session.add(song)
            sqldb.session.commit()

        # include date into user_song entry
        existingRecord = sqldb.session.query(UserSong).filter(UserSong.song_id == song.id,
                          UserSong.year == year, UserSong.period == period).with_parent(self.current_user).first()
        if existingRecord is None:
            songRecord = UserSong(desc=desc, user=self.current_user, date=[date], plays=plays, period=period, year=year, saved=saved)
            song.plays.append(songRecord)
            sqldb.session.add(songRecord)
            sqldb.session.commit()
        else:
            existingRecord.date.append(date)
            existingRecord.plays += 1
            sqldb.session.commit()

        # update the most recent added date
        self.current_user.recent = date if self.current_user.recent is None or date > self.current_user.recent else self.current_user.recent
        sqldb.session.commit()

    def get_most_recent(self):
        """
        Returns the date of the most recent song the user has played
        Returns:

        """
        recent = sqldb.session.query(User.recent).filter_by(id=self.current_user.id).first()
        try:
            return recent[0]
        except AttributeError:
            return None

    def save_song(self, sid):
        try:
            mark = sqldb.session.query(UserSong).with_parent(self.current_user).filter(UserSong.id==sid).first()
            mark.saved = True if mark.saved is None else None  # toggles save
            sqldb.session.commit()
        except AttributeError:
            raise Exception("Song not found")

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

    def clear_db(self):
        sqldb.drop_all()
