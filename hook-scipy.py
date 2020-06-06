'''
Pyinstaller hook
pyinstaller --onefile --additional-hooks-dir=.hook-scipy.py --icon=assets/icon.ico -w album-art-wallpaper.py
'''

from PyInstaller.utils.hooks import collect_submodules
from PyInstaller.utils.hooks import collect_data_files
hiddenimports = collect_submodules('scipy')

datas = collect_data_files('scipy')