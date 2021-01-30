from flask import Flask, redirect, request, render_template, url_for, Response, make_response
from dotenv import load_dotenv
import os
import psycopg2
from datetime import datetime, timedelta
from flask_dance.contrib.spotify import make_spotify_blueprint, spotify
from oauthlib.oauth2.rfc6749.errors import TokenExpiredError
from flask_login import current_user, login_user, logout_user, LoginManager, login_required
from flask_dance.consumer import oauth_authorized
from flask_dance.consumer.storage.sqla import SQLAlchemyStorage
from sqlalchemy.orm.exc import NoResultFound, UnmappedInstanceError
from flask_script import Manager
from flask_migrate import Migrate, MigrateCommand
# from flask_cors import CORS, cross_origin
from db import sqldb, User, OAuth, Database

load_dotenv()
app = Flask(__name__)
# CORS(app, resources={r"/search": {"origins": "http://127.0.0.1:5000"}})
app.secret_key = os.environ.get('SECRET_KEY')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
# app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('SQLALCHEMY_DATABASE_URI')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
conn = psycopg2.connect(os.environ.get('DATABASE_URL'), sslmode='require')
sqldb.init_app(app)
login_manager = LoginManager(app)
dbInterface = Database(current_user)
migrate = Migrate(app, sqldb, render_as_batch=True)
manager = Manager(app)
manager.add_command('db', MigrateCommand)

scope = "user-read-recently-played"
blueprint = make_spotify_blueprint(client_id=os.environ.get('SPOTIPY_CLIENT_ID'),
                                   client_secret=os.environ.get('SPOTIPY_CLIENT_SECRET'),
                                   scope=["user-read-recently-played", "user-read-email", "user-top-read"],
                                   redirect_url="/discover",
                                   storage=SQLAlchemyStorage(OAuth, sqldb.session, user=current_user,
                                                             user_required=False))
app.register_blueprint(blueprint=blueprint, url_prefix='/log_in')

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

REV_SEASONS = {'Spring': 3, 'Summer': 6, 'Fall': 9, 'Winter': 12}


#--- OAUTH / LOG IN ---#


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


@app.route('/login')
def login():
    return redirect(url_for('spotify.login'))


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect('/discover')


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
            topSongs()  # todo: have loading to show

        login_user(user)


#--- SPOTIFY API ---#

def makeRequest(url):
    spotify.get(url).json()


@app.route('/search', methods=['GET'])
# @cross_origin(origin='127.0.0.1',headers=['Content- Type','Authorization'])
def search():
    query = request.args.get('query')
    try:
        resp = spotify.get(f'/v1/search?q={query}&type=track&market=US').json()
        # resp.headers["Access-Control-Allow-Origin"] = "*"
    except TokenExpiredError:
        resp = make_response(redirect(url_for('spotify.login')))
        # print(resp.headers)
        resp.headers["Access-Control-Allow-Origin"] = "http://127.0.0.1:5000"
        # return redirect(url_for('travel'))
    return resp


@app.route('/save')
def save():
    spotify_id = request.args.get('id')
    try:
        dbInterface.save_song(spotify_id) # TODO: add error catching here
    except:
        return Response(status=500)
    return Response(status=200)


@app.route('/add_song', methods=['POST'])
def add_song():
    spotify_id = request.form.get('id')
    name = request.form.get('name')
    artist = request.form.get('artist')
    desc = request.form.get('desc')
    period = request.form.get('season')
    year = request.form.get('year')
    image = request.form.get('image')
    preview = request.form.get('preview')
    link = request.form.get('link')
    if not spotify_id or not name or not artist or not year:
        return redirect('/browse'), 400
    defSeason = REV_SEASONS[request.form.get('season')] if request.form.get('season') else 1
    date = '{}-{:02d}-{:02d}T00:00:00.000Z'.format(request.form.get('year'), defSeason, 1)  # 2020-08-26T00:25:10.291Z

    dbInterface.add_song(name=name, artist=artist, desc=desc, period=period, year=year, date=date, song_id=spotify_id,
                         saved=True, image=image, preview=preview, link=link)
    return redirect('/browse'), 200


@app.route('/resetSaved')
def reset():
    dbInterface.reset_saved(current_user)
    return Response(status=200)


def get_and_update_db(most_recent):
    try:
        # resp = spotify.get(f'/v1/me/player/recently-played?limit=50&before={int(timestamp)}').json() use when API beta is over and fixed
        resp = spotify.get(f'/v1/me/player/recently-played?limit=50').json()

    except TokenExpiredError:
        raise TokenExpiredError

    # get the most recent songs to update db
    for played in resp['items']:
        try:
            date = played['played_at']

            if date <= most_recent:
                break
            name = played['track']['name']
            song_id = played['track']['uri'].split(':')[2]  # todo: change to ID
            artist = played['track']['artists'][0]['name'] if len(played['track']['artists']) <= 1 else \
                played['track']['artists'][0]['name'] + " and others"
            desc = ''
            image = played['track']['album']['images'][-1]['url']  # get link to smallest image
            preview = played['track']['preview_url']
            link = played['track']['external_urls']['spotify']
            # parse datetime ex. 2020-08-20T21:43:25.567Z
            year, month, *_ = date.split('-')

            # declare period
            period = SEASONS[int(month)]
            dbInterface.add_song(name=name, song_id=song_id, artist=artist, desc=desc, period=period, year=year, date=date,
                                 image=image, preview=preview, link=link)
        except AttributeError:
            print("ERROR when adding songs")  # skip this one


def topSongs():
    time_periods = ['medium_term', 'short_term' ] # , 'long_term'] todo: find where to add long term
    try:
        top_songs = set()
        today = datetime.now()
        for term in time_periods:
            resp = spotify.get(f'/v1/me/top/tracks?time_range={term}').json()
            for song in resp['items']:
                try:
                    song_id = song['id']
                    if song_id not in top_songs:
                        name = song['name']
                        artist = song['artists'][0]['name'] if len(song['artists']) <= 1 else song['artists'][0]['name'] + " and others"
                        image = song['album']['images'][-1]['url']
                        year = (today - timedelta(days=180 if term == 'medium_term' else 30)).year
                        preview = song['preview_url']
                        link = song['external_urls']['spotify']
                        date = '{}-{:02d}-{:02d}T00:00:00.000Z'.format(year, 1, 1)  # 2020-08-26T00:25:10.291Z
                        top_songs.add(song_id)  # don't allow repeats
                        dbInterface.add_song(name=name, artist=artist, desc='', year=year, date=date,
                                         song_id=song_id, saved=True, image=image, preview=preview, link=link)
                except AttributeError:
                    print("ERROR with adding top song")  # skip

        # get from Your Top Songs playlist
        resp = spotify.get(f'/v1/search?q=your%20top%20songs&type=playlist').json()
        if resp:
            for item in resp.get('playlists', {'items':[]}).get('items', []):
                try:
                    if item['owner']['id'] == 'spotify' and item['name'][:14] == 'Your Top Songs':
                        # add songs in this playlist to the specified year
                        year = int(item['name'][15:])
                        playlist_id = item['id']
                        songResp = spotify.get(f'v1/playlists/{playlist_id}/tracks').json()
                        if songResp:
                            for song in songResp['items']:
                                try:
                                    popularity = int(song['track']['popularity'])
                                    if popularity > 50:
                                        name = song['track']['name']
                                        song_id = song['track']['id']
                                        artist = song['track']['artists'][0]['name'] if len(song['track']['artists']) <= 1 else \
                                            song['track']['artists'][0]['name'] + " and others"
                                        image = song['track']['album']['images'][-1]['url']  # get link to smallest image
                                        preview = song['track']['preview_url']
                                        link = song['track']['external_urls']['spotify']
                                        date = '{}-{:02d}-{:02d}T00:00:00.000Z'.format(year, 1, 1)  # 2020-08-26T00:25:10.291Z
                                        dbInterface.add_song(name=name, song_id=song_id, artist=artist, desc='', year=year, date=date,
                                                             image=image, preview=preview, link=link, saved=True)
                                except AttributeError:
                                    print("ERROR in adding playlist song top songs")
                except AttributeError:
                    print('ERROR in adding playlist top songs')

    except TokenExpiredError:
        raise TokenExpiredError



#--- VIEWS ---#


@app.route('/discover', methods=['GET', 'POST'])
def discover():
    if not spotify.authorized:
        return render_template('logged_out.html')

    try:
        # get year
        current_year = datetime.now().year
        try:
            most_recent = dbInterface.get_most_recent()
            # timestamp = datetime.strptime(most_recent, "%Y-%m-%dT%H:%M:%S.%fZ").timestamp() use when API beta is over and fixed
        except (UnmappedInstanceError, AttributeError):
            most_recent = '0'
            # timestamp = 0 use when API beta is over and fixed

        get_and_update_db(most_recent)

        # get the songs to display
        season = request.args.get('season')
        year = request.args.get('year')

        if season and year:
            target_period = season
        elif year:
            target_period = None
        elif season:
            return render_template('discover.html', songs=[], current_year=current_year, carMax=3), 400
        else:
            return render_template('discover.html', songs=[], current_year=current_year, carMax=3), 200

        # get songs in period
        songs = dbInterface.get_period_songs(target_period, year)

        return render_template('discover.html', songs=songs, current_year=current_year, carMax=3), 200
    except TokenExpiredError:
        return redirect(url_for('spotify.login'))


@app.route('/browse', methods=['GET', 'POST'])
def browse():
    if not spotify.authorized:
        return render_template('logged_out.html')

    try:
        songs = dbInterface.get_saved_songs()
        current_year = datetime.now().year
    except TokenExpiredError:
        return redirect(url_for('spotify.login'))

    return render_template('browse.html', resp=songs, current_year=current_year)


@app.route('/')
def home():
    return 'Hello World'


if __name__ == "__main__":
    # sqldb.init_app(app)
    migrate.init_app(app, sqldb)
    with app.app_context():
        sqldb.create_all()
    app.run(debug=True)
