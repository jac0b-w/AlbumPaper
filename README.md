# AlbumPaper (Windows 10)

**AlbumPaper only currently works with Windows 10**

This is a system tray app for windows that will change your desktop wallpaper based on the track you are listening to.
Works with Spotify or Last.fm.

<img src = readme_images/example.gif width='100%'>

As the artwork provided is only 640px if you are using a higher resolution than 1080p the artwork will be smaller. However there is an option to resize the image in the settings.
An internet connection is required.

## Getting Started

[Download installer for windows](https://github.com/jac0b-w/AlbumPaper/releases/latest)

There is a short initial setup:

1. Start the app (This takes a while ~15s). A music note icon will appear in the system tray and a window will open prompting you to select your service (Spotify or Last.fm) and enter your [API keys](https://github.com/jac0b-w/AlbumPaper/wiki/Getting-API-Keys)
2. Press 'Save' and start the app again.
    - If you are using the Spotify service this time your browser will open prompting you to login to your Spotify account.
3. Start playing music and your desktop wallpaper will change, you can click the icon in the system tray for more options.

If you are running the source you will also need to **(this is not required if you are using the installer)**:

- Install the dependencies ```pip install -r requirements.txt``` (Poetry users can use pyproject.toml)
- Rename ```_services.ini``` to ```services.ini```


### Getting your API Keys

[This section has been moved to the wiki](https://github.com/jac0b-w/AlbumPaper/wiki/Getting-API-Keys)

## Contributing

Any contributions are welcomed. Please ask questions and make suggestions in discussions and create an issue if you've encountered a problem.

## System Usage

Very low CPU and network usage until a new image is generated (song is skipped)

CPU Usage spikes: ~3% Art/Wallpaper background, ~20-25% Gradient/Solid background

Network Usage spikes: <1mbps

## Examples

<img src = readme_images/example2.jpg>

<img src = readme_images/example.jpg>
