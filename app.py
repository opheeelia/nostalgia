from flask import Flask, redirect, request, render_template, url_for
from dotenv import load_dotenv
import os
from datetime import datetime
from flask_dance.contrib.spotify import make_spotify_blueprint, spotify
from oauthlib.oauth2.rfc6749.errors import TokenExpiredError
from flask_login import current_user, login_user, logout_user, LoginManager, login_required
from flask_dance.consumer import oauth_authorized
from flask_dance.consumer.storage.sqla import SQLAlchemyStorage
from sqlalchemy.orm.exc import NoResultFound, UnmappedInstanceError
from flask_script import Manager
from flask_migrate import Migrate, MigrateCommand
from db import sqldb, User, OAuth, Database

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///sqldb.db'
sqldb.init_app(app)
login_manager = LoginManager(app)
dbInterface = Database(current_user)
migrate = Migrate(app, sqldb, render_as_batch=True)
manager = Manager(app)
manager.add_command('db', MigrateCommand)

load_dotenv()

scope = "user-read-recently-played"
blueprint = make_spotify_blueprint(client_id=os.environ.get('SPOTIPY_CLIENT_ID'),
                                   client_secret=os.environ.get('SPOTIPY_CLIENT_SECRET'),
                                   scope=["user-read-recently-played", "user-read-email"],
                                   redirect_url="/travel",
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

### OAUTH / LOG IN ###


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
    return redirect('/travel')


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


### SPOTIFY API ###


@app.route('/search', methods=['GET'])
def search():
    query = request.args.get('query')
    try:
        resp = spotify.get(f'/v1/search?q={query}&type=track&market=US', headers={'Access-Control-Allow-Origin': '*'}).json()
    except TokenExpiredError:
        return redirect(url_for('spotify.login'))
    return resp


@app.route('/save')
def save():
    spotify_id = request.args.get('id')
    dbInterface.save_song(spotify_id)
    return {"status": 200} #TODO: look into actual status responses


@app.route('/add_song', methods=['POST'])
def add_song():
    spotify_id = request.form.get('id')
    name = request.form.get('name')
    artist = request.form.get('artist')
    desc = request.form.get('desc')
    period = request.form.get('season') + " " + request.form.get('year')
    date = '{}-{:02d}-{:02d}T00:00:00.000Z'.format(request.form.get('year'), REV_SEASONS[request.form.get('season')], 1) # 2020-08-26T00:25:10.291Z

    dbInterface.add_song(name=name, artist=artist, desc=desc, period=period, date=date, song_id=spotify_id, saved=True)
    return redirect('/browse')


@app.route('/resetSaved')
def reset():
    dbInterface.reset_saved(current_user)
    return "done"


# def topSongs():
#     time_periods = ['short_term', 'medium_term', 'long_term']
#     try:
#         top_songs = {}
#         for term in time_periods:
#             resp = spotify.get(f'/v1/me/top/tracks?time_range={term}').json()
#             for song in resp['items']:
#                 name = song['name']
#                 song_id = song['id']
#                 artist = song['artists'][0]['name'] if len(song['artists']) <= 1 else song['artists'][0]['name'] + " and others"
#             # top_songs[term] =

@app.route('/travel', methods=['GET', 'POST'])
def travel():

    if not spotify.authorized:
        return render_template('logged_out.html')

    # get year
    current_year = datetime.now().year
    try:
        most_recent = dbInterface.get_most_recent()
        # timestamp = datetime.strptime(most_recent, "%Y-%m-%dT%H:%M:%S.%fZ").timestamp() use when API beta is over and fixed
    except (UnmappedInstanceError, AttributeError):
        most_recent = '0'
        # timestamp = 0 use when API beta is over and fixed

    try:
        # resp = spotify.get(f'/v1/me/player/recently-played?limit=50&before={int(timestamp)}').json() use when API beta is over and fixed
        resp = spotify.get(f'/v1/me/player/recently-played?limit=50').json()

    except TokenExpiredError:
        return redirect(url_for('spotify.login'))

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
        dbInterface.add_song(name=name, song_id=song_id, artist=artist, desc=desc, period=period, date=date)

    # get the songs to display
    season = request.args.get('season')
    year = request.args.get('year')

    if season and year:
        target_period = season + ' ' + year
    else:
        target_period = None

    # get songs in period
    songs = dbInterface.get_period_songs(target_period)

    print(f'{songs}')
    return render_template('travel.html', songs=songs, current_year=current_year, carMax=3)


@app.route('/browse', methods=['GET', 'POST'])
def browse():
    if not spotify.authorized:
        return render_template('logged_out.html')

    songs = dbInterface.get_saved_songs()
    current_year = datetime.now().year

    return render_template('browse.html', songs=songs, current_year=current_year)


if __name__ == "__main__":
    sqldb.init_app(app)
    migrate.init_app(app, sqldb)
    with app.app_context():
        sqldb.create_all()
    app.run(debug=True)
