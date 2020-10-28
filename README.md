# Album Art Wallpaper

This is a system tray app for windows that will change your desktop wallpaper based on the track you are listening to.
Works with Spotify or Last.fm.

<img src = readme_images/example.gif width='100%'>

As the artwork provided is only 640px if you are using a higher resolution than 1080p the artwork will be smaller. However there is an option to resize the image in the settings.
An internet connection is required.

## Getting Started

[Download installer for windows](https://github.com/jac0b-w/album-art-wallpaper/releases/latest)

There is a short initial setup:

1. Start the app (This takes a while ~15s). A music note icon will appear in the system tray and a window will open prompting you to select your service (Spotify or Last.fm) and enter your API keys (see section below)
2. Press 'Save' and start the app again.
    - If you are using the Spotify service this time your browser will open prompting you to login to your Spotify account.
3. Start playing music and your desktop wallpaper will change, you can click the icon in the system tray for more options.

If you are running the source you will also need to (this is not required if you are using the installer):

- Install the dependencies ```pip install -r requirements.txt```
- Rename ```_services.ini``` to ```services.ini```


### Getting your API Keys
#### Spotify
Head over to the [Spotify developer dashboard](https://developer.spotify.com/dashboard/login) and create a non-commercial app, call it whatever you like, select any use case and give it a description.

<img src = readme_images/image1.png width=300>

Once you are on the app page go to EDIT SETTINGS > Redirect URIs, enter ``` http://localhost:8080/ ``` __exactly__ and make sure to save it.

<img src = readme_images/image2.png width=300>

Copy and paste the Client ID and Client Secret into the settings.

<img src = readme_images/image3.png width=700>

#### Last.fm

Create a new API account [here](https://www.last.fm/api/account/create) enter an email and an application name a callback URI is __not__ required.

Add the API Key to the settings you do __not__ need the shared secret key.

Add your last.fm username to settings.

## Contibuting

Any contributions are welcomed. If you have any questions just ask in an issue.

## System Usage

No CPU or network usage until a new image is generated (song is skipped)

CPU Usage: ~3-6% on my system

Network Usage: <1mbps

## Examples

<img src = readme_images/example2.jpg>

<img src = readme_images/example.jpg>
