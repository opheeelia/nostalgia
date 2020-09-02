from flask import Flask, redirect, request, render_template, url_for
from dotenv import load_dotenv
import os
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_dance.contrib.spotify import make_spotify_blueprint, spotify
from flask_dance.consumer import oauth_authorized
from oauthlib.oauth2.rfc6749.errors import TokenExpiredError
from flask_login import UserMixin, current_user, login_user, logout_user, LoginManager, login_required
from flask_dance.consumer.storage.sqla import OAuthConsumerMixin, SQLAlchemyStorage
from flask_dance.consumer import oauth_authorized
from sqlalchemy.orm.exc import NoResultFound, UnmappedInstanceError
from sqlalchemy import func
from flask_script import Manager
from flask_migrate import Migrate, MigrateCommand

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///sqldb.db'
sqldb = SQLAlchemy(app)
login_manager = LoginManager(app)
migrate = Migrate(app, sqldb)
manager = Manager(app)

manager.add_command('db', MigrateCommand)

load_dotenv()

SEASONS = {1: 'Winter',
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


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


scope = "user-read-recently-played"
blueprint = make_spotify_blueprint(client_id=os.environ.get('SPOTIPY_CLIENT_ID'),
                                   client_secret=os.environ.get('SPOTIPY_CLIENT_SECRET'),
                                   scope=["user-read-recently-played", "user-read-email"],
                                   redirect_url="/travel",
                                   storage=SQLAlchemyStorage(OAuth, sqldb.session, user=current_user,
                                                             user_required=False))
app.register_blueprint(blueprint=blueprint, url_prefix='/log_in')


@app.route('/login')
def login():
    return redirect(url_for('spotify.login'))


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect('/travel')


@app.route('/search')
def search():
    query = request.args.get('query')
    return spotify.get(f'/v1/search?q={query}&type=track&market=US').json()


@app.route('/save')
def save():
    return {"status": 200}
    spotify_id = request.args.get('id')
    mark = sqldb.session.query(Song).with_parent(current_user).filter_by(spotify_id=spotify_id).one()
    mark.saved = True
    sqldb.session.commit()
    return 1
    # Song.update().where().values()

@oauth_authorized.connect_via(blueprint)
def logged_in(this_blueprint, token):
    resp = this_blueprint.session.get('/v1/me/')

    if resp.ok:
        user_id = resp.json()['id']
        query = User.query.filter_by(username=user_id)

        try:
            user = query.one()
        except NoResultFound:
            user = User(username=user_id)
            sqldb.session.add(user)
            sqldb.session.commit()

        login_user(user)


@app.route('/travel', methods=['GET', 'POST'])
def travel():

    if not spotify.authorized:
        return render_template('logged_out.html')

    # get year
    current_year = datetime.now().year
    try:
        most_recent = sqldb.session.query(Song).with_parent(current_user).order_by(Song.date.desc()).first().date
        # timestamp = datetime.strptime(most_recent, "%Y-%m-%dT%H:%M:%S.%fZ").timestamp() use when API beta is over and fixed
    except (UnmappedInstanceError, AttributeError):
        most_recent = '0'
        # timestamp = 0 use when API beta is over and fixed

    try:
        # resp = spotify.get(f'/v1/me/player/recently-played?limit=50&before={int(timestamp)}').json() use when API beta is over and fixed
        resp = spotify.get(f'/v1/me/player/recently-played?limit=50').json()

    except TokenExpiredError:
        return redirect(url_for('spotify.login'))

    print(current_user.username)

    # get the most recent songs to update db
    for played in resp['items']:
        date = played['played_at']

        if date <= most_recent:
            break

        name = played['track']['name']
        song_id = played['track']['uri'].split(':')[2]
        artist = played['track']['artists'][0]['name'] if len(played['track']['artists']) <= 1 else \
            played['track']['artists'][0]['name'] + " and others"
        desc = ""
        # parse datetime ex. 2020-08-20T21:43:25.567Z
        year, month, *_ = date.split('-')

        # declare period
        period = SEASONS[int(month)] + ' ' + year
        sqlsong = Song(name=name, artist=artist, desc=desc, song_user=current_user, date=date, spotify_id=song_id,
                       period=period, saved=False)
        sqldb.session.add(sqlsong)
        sqldb.session.commit()

    # get the songs to display
    season = request.args.get('season')
    year = request.args.get('year')

    if season and year:
        target_period = season + ' ' + year
    else:
        target_period = None

    # get songs in period
    display_songs = sqldb.session.query(Song.name, Song.artist, func.count(Song.spotify_id), Song.spotify_id).with_parent(current_user) \
        .filter_by(period=target_period).group_by(Song.spotify_id).having(func.count(Song.spotify_id) > 1)\
        .order_by(func.count(Song.spotify_id).desc()).all()

    return render_template('travel.html', songs=display_songs, current_year=current_year, carMax=3)


@app.route('/browse', methods=['GET', 'POST'])
def browse():
    if not spotify.authorized:
        return render_template('logged_out.html')

    periods = sqldb.session.query(Song.period, func.count(Song.period)).with_parent(current_user).filter_by(saved=True)\
        .group_by(Song.period).all()

    return render_template('browse.html', periods=periods)

if __name__ == "__main__":
    sqldb.create_all()
    app.run(debug=True)
