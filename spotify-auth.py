import webbrowser, spotipy, os, configparser
from flask import Flask, request, redirect

config = configparser.ConfigParser()
config.read('config.ini')

app = Flask(__name__)

os.environ["CLIENT_ID"] = config["Spotify API Keys"]["CLIENT_ID"]
os.environ["CLIENT_SECRET"] = config["Spotify API Keys"]["CLIENT_SECRET"]


CLI_ID = os.getenv('CLIENT_ID')
CLI_SEC = os.getenv('CLIENT_SECRET')
REDIRECT_URI = "http://localhost:5000/callback/"
SCOPE = "user-read-currently-playing"
SHOW_DIALOG = False


def shutdown_server():
    func = request.environ.get('werkzeug.server.shutdown')
    func()

@app.route("/")
def _home():
    return redirect(f'https://accounts.spotify.com/authorize?client_id={CLI_ID}&response_type=code&redirect_uri={REDIRECT_URI}&scope={SCOPE}&show_dialog={SHOW_DIALOG}')

@app.route("/callback/")
def _callback():
    code = request.args.get('code')
    token = sp_oauth.get_access_token(code, as_dict=False)

    shutdown_server()
    return "Account successfully authorized. You can close this window."

    
sp_oauth = spotipy.SpotifyOAuth(
    CLI_ID,
    CLI_SEC,
    redirect_uri = REDIRECT_URI,
    scope=SCOPE,
    cache_path=".cache",
    show_dialog=SHOW_DIALOG
)

cached_token = sp_oauth.get_cached_token()

if cached_token:
    token = cached_token["access_token"]
else:
    webbrowser.open("http://localhost:5000/")
    app.run(debug=True)