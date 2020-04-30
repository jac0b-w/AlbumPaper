# Album Art Wallpaper

This is a system tray app for windows that will change your desktop wallpaper based on the track you are listening to on Spotify.


As the artwork provided is only 640px if you are using a higher resolution than 1080p the artwork will be smaller. However there is an option to resize the image in the settings.
An internet connection is required.

## Getting Started

[Download exe](https://github.com/jac0b-w/album-art-wallpaper/releases/latest)

[Download source](https://github.com/jac0b-w/album-art-wallpaper/archive/master.zip)

There is a short initial setup:

1. Set your redirect URI and get your api keys and add them to config.ini (read below)
2. Open ```album-art-wallpaper.exe```, ignore the error message a spotify webpage will pop up where you can authorise your Spotify account
3. ```Open album-art-wallpaper.exe``` again, you should be good to go.

- If you want it to run at startup create a shortcut of ```album-art-wallpaper.exe``` and copy it into ```%appdata%\Microsoft\Windows\Start Menu\Programs\Startup```

If you are running the source you will also need to:

- Install the dependencies ```pip install -r requirements.txt```
- Rename ```config_sample.ini``` to ```config.ini```

### Getting your API Keys
Head over to the [Spotify developer dashboard](https://www.google.com) and create a non-commercial app, call it whatever you like, select any use case and give it a description.

<img src = readme_images/image1.png width=300>

Once you are on the app page go to EDIT SETTINGS > Redirect URIs, enter ``` http://localhost:5000/callback/ ``` exactly and make sure to save it.

<img src = readme_images/image2.png width=300>

Copy and paste the Client ID and Client Secret into the config.ini file. You can easily find this by clicking on settings in the context menu.

<img src = readme_images/image3.png width=700>


### Settings
There are two settings in the config.ini file:

- ```request_interval``` controls how often a request is sent to the Spotify Web API.
- ```resize_art``` when true will resize the 640px album art to fit on the smallest axis.

## Example
![](readme_images/example_wallpaper.png)
![](readme_images/example_wallpaper2.png)
