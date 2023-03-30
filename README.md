# AlbumPaper

This is a system tray app for windows that will change your desktop wallpaper based on the track you are listening to.
Works with Spotify or Last.fm. An internet connection is required.

## [Download](https://github.com/jac0b-w/AlbumPaper/releases/latest)

https://user-images.githubusercontent.com/51512690/228698806-3bbfc2c8-f0b5-477d-b965-6ccc9146c609.mp4

#### [Buy me a coffee]((https://www.buymeacoffee.com/jac0b))
[<img src = "https://i.giphy.com/media/TDQOtnWgsBx99cNoyH/giphy.webp" height="65px">](https://www.buymeacoffee.com/jac0b)

## Getting Started

[Download installer (windows)](https://github.com/jac0b-w/AlbumPaper/releases/latest)

There is a short initial setup:

1. Start the app (This takes a while ~15s). A music note icon will appear in the system tray and a window will open prompting you to select your service (Spotify or Last.fm) and enter your [API keys](https://github.com/jac0b-w/AlbumPaper/wiki/Getting-API-Keys)
2. Press 'Save' and start the app again.
    - If you are using the Spotify your browser will open prompting you to login to your Spotify account. 
3. Start playing music and your desktop wallpaper will change, you can click the icon in the system tray for more options.
    - For some people this doesn't always work first time. Here are some troubleshooting tips you can try:
        - Quit the app and open it again
        - Restart your pc
        - Failing that please create an issue

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

<img src = readme_images/eg.jpg>
