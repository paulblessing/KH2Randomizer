import os

from Module.resources import resource_path

# Keep the setting of the environment variable as close to the top as possible.
# This needs to happen before anything Boss/Enemy Rando gets loaded for the sake of the distributed binary.
os.environ["USE_KH2_GITPATH"] = resource_path("extracted_data")

import datetime
import json
import random
import re
import string
import sys

import pyperclip as pc
import pytz
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QMainWindow, QApplication,
    QLabel, QLineEdit, QMenu, QPushButton, QCheckBox, QTabWidget, QVBoxLayout, QHBoxLayout, QWidget, QInputDialog,
    QMenuBar, QMessageBox
)

from Class.seedSettings import SeedSettings
from Module.dailySeed import getDailyModifiers
from Module.seedshare import SharedSeed, ShareStringException
from UI.FirstTimeSetup.firsttimesetup import FirstTimeSetup
from UI.SeedSummaryView import SeedSummaryView
from UI.Submenus.BossEnemyMenu import BossEnemyMenu
from UI.Submenus.HintsMenu import HintsMenu
from UI.Submenus.ItemPlacementMenu import ItemPlacementMenu
from UI.Submenus.KeybladeMenu import KeybladeMenu
from UI.Submenus.MiscMenu import MiscMenu
from UI.Submenus.SeedModMenu import SeedModMenu
from UI.Submenus.SoraMenu import SoraMenu
from UI.Submenus.StartingMenu import StartingMenu
from UI.Submenus.WorldMenu import WorldMenu

LOCAL_UI_VERSION = '1.99.3'


class Logger(object):
    def __init__(self, orig_stream):
        self.filename = "log.txt"
        self.orig_stream = orig_stream
    def write(self, data):
        with open(self.filename, "a") as f:
            f.write(str(data))
        self.orig_stream.write(str(data))
    def flush(self):
        self.orig_stream.flush()

logger = Logger(sys.stdout)

sys.stdout = logger
sys.stderr = logger


AUTOSAVE_FOLDER = "auto-save"
PRESET_FOLDER = "presets"


class KH2RandomizerApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.startTime = datetime.datetime.now(pytz.UTC)

        self.settings = SeedSettings()

        if not os.path.exists(AUTOSAVE_FOLDER):
            os.makedirs(AUTOSAVE_FOLDER)
        auto_settings_save_path = os.path.join(AUTOSAVE_FOLDER, 'auto-save.json')
        if os.path.exists(auto_settings_save_path):
            with open(auto_settings_save_path, 'r') as source:
                try:
                    auto_settings_json = json.loads(source.read())
                    self.settings.apply_settings_json(auto_settings_json, include_private=True)
                except Exception:
                    print('Unable to apply last settings - will use defaults')
                    pass

        with open(resource_path("UI/stylesheet.qss"),"r") as style:
            data = style.read()
            self.setStyleSheet(data)

        random.seed(str(datetime.datetime.now()))
        self.setWindowTitle("KH2 Randomizer Seed Generator ({0})".format(LOCAL_UI_VERSION))
        self.setWindowIcon(QIcon(resource_path("Module/icon.png")))
        self.setMinimumWidth(1000)
        self.setup = None
        pagelayout = QVBoxLayout()
        seed_layout = QHBoxLayout()
        submit_layout = QHBoxLayout()
        self.tabs = QTabWidget()

        self.menuBar = QMenuBar()
        self.presetMenu = QMenu("Preset")
        self.presetMenu.addAction("Open Preset Folder", self.openPresetFolder)
        self.presetsMenu = QMenu("Presets")
        self.seedMenu = QMenu("Load Seed")
        self.seedMenu.addAction("Load Seed from Clipboard", self.receiveSeed)
        self.seedMenu.addAction("Load Daily Seed", self.loadDailySeed)
        self.presetMenu.addAction("Save Settings as New Preset", self.savePreset)
        self.presetMenu.addMenu(self.presetsMenu)
        self.menuBar.addMenu(self.seedMenu)
        self.menuBar.addMenu(self.presetMenu)

        self.menuBar.addAction("About", self.showAbout)

        self.preset_json = {}
        if not os.path.exists(PRESET_FOLDER):
            os.makedirs(PRESET_FOLDER)
        for file in os.listdir(PRESET_FOLDER):
            preset_name, extension = os.path.splitext(file)
            if extension == '.json':
                with open(os.path.join(PRESET_FOLDER, file), 'r') as presetData:
                    settings_json = json.loads(presetData.read())
                    self.preset_json[preset_name] = settings_json

        pagelayout.addWidget(self.menuBar)
        pagelayout.addLayout(seed_layout)
        pagelayout.addWidget(self.tabs)
        pagelayout.addLayout(submit_layout)
        seed_layout.addWidget(QLabel("Seed"))
        self.seedName=QLineEdit()
        self.seedName.setPlaceholderText("Leave blank for a random seed")
        seed_layout.addWidget(self.seedName)

        for x in self.preset_json.keys():
            if x != 'BaseDailySeed':
                self.presetsMenu.addAction(x, lambda x=x: self.usePreset(x))

        self.spoiler_log = QCheckBox("Make Spoiler Log")
        self.spoiler_log.setCheckState(Qt.Checked)
        seed_layout.addWidget(self.spoiler_log)

        self.widgets = [
            SoraMenu(self.settings),
            StartingMenu(self.settings),
            HintsMenu(self.settings),
            KeybladeMenu(self.settings),
            WorldMenu(self.settings),
            MiscMenu(self.settings),
            SeedModMenu(self.settings),
            ItemPlacementMenu(self.settings),
            BossEnemyMenu(self.settings),
        ]

        for i in range(len(self.widgets)):
            self.tabs.addTab(self.widgets[i],self.widgets[i].getName())

        submit = QPushButton("Continue")
        submit.clicked.connect(self.makeSeed)
        submit_layout.addWidget(submit)

        widget = QWidget()
        widget.setLayout(pagelayout)
        self.setCentralWidget(widget)

    def closeEvent(self, e):
        settings_json = self.settings.settings_json(include_private=True)
        with open(os.path.join(AUTOSAVE_FOLDER, 'auto-save.json'), 'w') as presetData:
            presetData.write(json.dumps(settings_json, indent=4, sort_keys=True))
        e.accept()

    def loadDailySeed(self):
        daily_settings = SeedSettings()
        daily_settings.apply_settings_json(self.preset_json['BaseDailySeed'])
        daily_settings.apply_private_settings(self.settings)

        # use the modifications to change the preset
        mod_string = f'Updated settings for Daily Seed {self.startTime.strftime("%a %b %d %Y")}\n\n'
        for m in getDailyModifiers(self.startTime):
            m.local_modifier(daily_settings)
            mod_string += m.name + ' - ' + m.description + '\n'

        message = QMessageBox(text=mod_string)
        message.setWindowTitle('KH2 Seed Generator - Daily Seed')
        message.exec()

        summary_view = SeedSummaryView(
            parent=self,
            local_ui_version=LOCAL_UI_VERSION,
            seed_name=self.startTime.strftime('%d%m%Y'),
            settings=daily_settings,
            spoiler_log=True
        )
        summary_view.exec()

    def fixSeedName(self):
        new_string = re.sub(r'[^a-zA-Z0-9]', '', self.seedName.text())
        self.seedName.setText(new_string)

    def makeSeed(self):
        self.fixSeedName()

        seed_name = self.seedName.text()
        if seed_name == "":
            characters = string.ascii_letters + string.digits
            seed_name = (''.join(random.choice(characters) for i in range(30)))

        summary_view = SeedSummaryView(
            parent=self,
            local_ui_version=LOCAL_UI_VERSION,
            seed_name=seed_name,
            settings=self.settings,
            spoiler_log=self.spoiler_log.isChecked()
        )
        summary_view.exec()

    def savePreset(self):
        preset_name, ok = QInputDialog.getText(self, 'Make New Preset', 'Enter a name for your preset...')

        if ok:
            # add current settings to saved presets, add to current preset list, change preset selection.
            settings_json = self.settings.settings_json()
            self.preset_json[preset_name] = settings_json
            self.presetsMenu.addAction(preset_name, lambda: self.usePreset(preset_name))
            with open(os.path.join(PRESET_FOLDER, preset_name + '.json'), 'w') as presetData:
                presetData.write(json.dumps(settings_json, indent=4, sort_keys=True))

    def openPresetFolder(self):
        os.startfile(PRESET_FOLDER)

    def usePreset(self, preset_name: str):
        settings_json = self.preset_json[preset_name]
        self.settings.apply_settings_json(settings_json)
        for widget in self.widgets:
            widget.update_widgets()

    def receiveSeed(self):
        try:
            shared_seed = SharedSeed.from_share_string(
                local_generator_version=LOCAL_UI_VERSION,
                share_string=pc.paste()
            )
        except ShareStringException as exception:
            message = QMessageBox(text=exception.message)
            message.setWindowTitle("KH2 Seed Generator")
            message.exec()
            return

        summary_settings = SeedSettings()
        summary_settings.apply_settings_string(shared_seed.settings_string)
        summary_settings.apply_private_settings(self.settings)

        summary_view = SeedSummaryView(
            parent=self,
            local_ui_version=LOCAL_UI_VERSION,
            seed_name=shared_seed.seed_name,
            settings=summary_settings,
            spoiler_log=shared_seed.spoiler_log
        )
        summary_view.exec()

    def firstTimeSetup(self):
        print("First Time Setup")
        if self.setup is None:
            self.setup = FirstTimeSetup()
            self.setup.show()

    def showAbout(self):
        aboutText = '''
Kingdom Hearts II Final Mix Zip Seed Generator Version {0}<br>
Created by Thundrio, Tommadness, and ZakTheRobot<br><br>

Thank you to all contributors, testers, and advocates.<br><br>

<a href="https://github.com/tommadness/KH2Randomizer">Github Link</a><br>
<a href="https://discord.gg/KwfqM6GYzd">KH2 Randomizer Discord</a><br><br>

<a href="https://github.com/tommadness/KH2Randomizer/tree/local_ui#acknowledgements">Acknowledgements</a>



'''.format(LOCAL_UI_VERSION)
        message = QMessageBox(text=aboutText)
        message.setTextFormat(Qt.RichText)
        message.setWindowTitle("About")
        message.setWindowIcon(QIcon(resource_path("Module/icon.png")))
        message.exec()


if __name__=="__main__":
    app = QApplication([])
    window = KH2RandomizerApp()
    window.show()
    #commenting out first time setup for 2.999 version
    # configPath = Path("rando-config.yml")
    # if not configPath.is_file() or not os.environ.get("ALWAYS_SETUP") is None:
    #     window.firstTimeSetup()

    sys.exit(app.exec())
