import os
import sys


# Keep resource_path definition and the setting of the environment variable as close to the top as possible.
# These need to happen before anything Boss/Enemy Rando gets loaded for the sake of the distributed binary.
def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)


os.environ["USE_KH2_GITPATH"] = resource_path("extracted_data")


import datetime
import json
import random
import re
import string
from pathlib import Path

import pyperclip as pc
import pytz
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QMainWindow, QApplication,
    QLabel, QLineEdit, QMenu, QPushButton, QCheckBox, QTabWidget, QVBoxLayout, QHBoxLayout, QWidget, QInputDialog,
    QFileDialog, QMenuBar, QMessageBox, QProgressDialog, QGroupBox
)

from Class import seedSettings, settingkey
from Class.seedSettings import SeedSettings
from List.configDict import locationType
from List.hashTextEntries import HASH_ICON_COUNT, generateHashIcons
from Module.dailySeed import getDailyModifiers
from Module.randomizePage import randomizePage
from Module.seedshare import SharedSeed, ShareStringException
from UI.FirstTimeSetup.firsttimesetup import FirstTimeSetup
from UI.Submenus.BossEnemyMenu import BossEnemyMenu
from UI.Submenus.CosmeticsMenu import CosmeticsMenu
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


class GenSeedThread(QThread):
    finished = Signal(object)

    def provideData(self,data,session):
        self.data=data
        self.session = session
        self.zip_file = None

    def run(self):
        zip_file = randomizePage(self.data,self.session,local_ui=True)
        self.finished.emit(zip_file)


class KH2RandomizerApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.UTC = pytz.utc
        self.startTime = datetime.datetime.now(self.UTC)
        self.dailySeedName = self.startTime.strftime('%d-%m-%Y')
        self.mods = getDailyModifiers(self.startTime)

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
        self.seedMenu = QMenu("Share Seed")
        self.seedMenu.addAction("Save Seed to Clipboard", self.shareSeed)
        self.seedMenu.addAction("Load Seed from Clipboard", self.receiveSeed)
        self.presetMenu.addAction("Save Settings as New Preset", self.savePreset)
        self.presetMenu.addMenu(self.presetsMenu)
        self.menuBar.addMenu(self.seedMenu)
        self.menuBar.addMenu(self.presetMenu)

        # populate a menu item for the daily seed
        self.menuBar.addAction("Load Daily Seed", self.loadDailySeed)

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
            CosmeticsMenu(self.settings),
        ]

        for i in range(len(self.widgets)):
            self.tabs.addTab(self.widgets[i],self.widgets[i].getName())

        seedhashlayout = QHBoxLayout()
        seedhashlayout.addWidget(QLabel("Seed Hash"))
        self.hashIconPath = Path(resource_path("static/seed-hash-icons"))
        self.hashIcons = [QLabel() for _ in range(HASH_ICON_COUNT)]
        for label in self.hashIcons:
            label.blockSignals(True)
            seedhashlayout.addWidget(label)
        seed_hash_box = QGroupBox()
        seed_hash_box.setLayout(seedhashlayout)
        submit_layout.addWidget(seed_hash_box)

        submit_button_pcsx2 = QPushButton("Generate Seed (PCSX2)")
        submit_button_pcsx2.clicked.connect(lambda: self.makeSeed("PCSX2"))
        submit_layout.addWidget(submit_button_pcsx2, stretch=2)

        submit_button_pc = QPushButton("Generate Seed (PC)")
        submit_button_pc.clicked.connect(lambda: self.makeSeed("PC"))
        submit_layout.addWidget(submit_button_pc, stretch=2)

        widget = QWidget()
        widget.setLayout(pagelayout)
        self.setCentralWidget(widget)

        self.update_hash_icons()

        self.seedName.textChanged.connect(self.seed_name_text_changed)
        self.spoiler_log.stateChanged.connect(self.spoiler_log_state_changed)

    def closeEvent(self, e):
        settings_json = self.settings.settings_json(include_private=True)
        with open(os.path.join(AUTOSAVE_FOLDER, 'auto-save.json'), 'w') as presetData:
            presetData.write(json.dumps(settings_json, indent=4, sort_keys=True))
        e.accept()

    def loadDailySeed(self):
        self.seedName.setText(self.dailySeedName)
        self.settings.apply_settings_json(self.preset_json['BaseDailySeed'])

        # use the modifications to change the preset
        mod_string = f'Updated settings for Daily Seed {self.startTime.strftime("%a %b %d %Y")}\n\n'
        for m in self.mods:
            m.local_modifier(self.settings)
            mod_string += m.name + ' - ' + m.description + '\n'

        for widget in self.widgets:
            widget.update_widgets()

        message = QMessageBox(text=mod_string)
        message.setWindowTitle('KH2 Seed Generator - Daily Seed')
        message.exec()

    def seed_name_text_changed(self):
        # Remove any non-alphanumeric characters and limit the size to 91 (7 X 13) so that seed share strings don't get
        # super long. (Did you know that 7 and 13 are important numbers in the KH series?)
        new_string = re.sub(r'[^a-zA-Z0-9]', '', self.seedName.text())[:91]
        self.seedName.setText(new_string)
        self.update_hash_icons()

    def spoiler_log_state_changed(self):
        self.update_hash_icons()

    def random_seed_name(self):
        characters = string.ascii_letters + string.digits
        # Using a local Random instance which won't be affected by our changes to the seed of the global Random
        return ''.join(random.Random().choices(characters, k=30))

    def seed_rng_string(self, seed_name: str) -> str:
        # Seed is based on seed name, UI version, and if a spoiler log is generated or not.
        return seed_name + LOCAL_UI_VERSION + str(self.spoiler_log.isChecked())

    def update_hash_icons(self):
        seed_name = self.seedName.text()
        if seed_name == '':
            icon_names = ['question-mark' for _ in range(HASH_ICON_COUNT)]
        else:
            # Using a local Random instance here just to be extra safe with not messing with the global RNG
            local_random = random.Random(self.seed_rng_string(seed_name))
            icon_names = generateHashIcons(local_random)

        icons_dir = str(self.hashIconPath.absolute())
        for index, icon_name in enumerate(icon_names):
            path = icons_dir + '/' + icon_name + '.png'
            pixmap = QPixmap(path).scaledToHeight(40, Qt.TransformationMode.SmoothTransformation)
            self.hashIcons[index].setPixmap(pixmap)

    def make_seed_session(self):
        makeSpoilerLog = self.spoiler_log.isChecked()

        session={}

        # seed
        seed_name = self.seedName.text()
        if seed_name == '':
            seed_name = self.random_seed_name()
            self.seedName.setText(seed_name)
        random.seed(self.seed_rng_string(seed_name))
        session['seed'] = seed_name

        # seedHashIcons
        session["seedHashIcons"] = generateHashIcons()

        # includeList
        include_list = []
        session["includeList"] = include_list
        include_list_keys = [
            (settingkey.FORM_LEVEL_REWARDS, 'Form Levels'),
            (settingkey.CRITICAL_BONUS_REWARDS, 'Critical Bonuses'),
            (settingkey.GARDEN_OF_ASSEMBLAGE_REWARDS, 'Garden of Assemblage'),
        ]
        for key in include_list_keys:
            if self.settings.get(key[0]):
                include_list.append(key[1])
        for location in self.settings.get(settingkey.WORLDS_WITH_REWARDS):
            include_list.append(locationType[location].value)
        for location in self.settings.get(settingkey.SUPERBOSSES_WITH_REWARDS):
            include_list.append(locationType[location].value)
        for location in self.settings.get(settingkey.MISC_LOCATIONS_WITH_REWARDS):
            include_list.append(locationType[location].value)

        # levelChoice
        session['levelChoice'] = self.settings.get(settingkey.SORA_LEVELS)

        # startingInventory
        session['startingInventory'] = [int(value) for value in self.settings.get(settingkey.STARTING_INVENTORY)]

        # itemPlacementDifficulty
        session['itemPlacementDifficulty'] = self.settings.get(settingkey.ITEM_PLACEMENT_DIFFICULTY)

        # seedModifiers
        seed_modifiers = []
        session['seedModifiers'] = seed_modifiers
        seed_modifier_keys = [
            (settingkey.MAX_LOGIC_ITEM_PLACEMENT, 'Max Logic Item Placement'),
            (settingkey.REVERSE_RANDO, 'Reverse Rando'),
            (settingkey.LIBRARY_OF_ASSEMBLAGE, 'Library of Assemblage'),
            (settingkey.SCHMOVEMENT, 'Schmovement'),
            (settingkey.GLASS_CANNON, 'Glass Cannon'),
            (settingkey.BETTER_JUNK, 'Better Junk'),
            (settingkey.START_NO_AP, 'Start with No AP'),
            (settingkey.REMOVE_DAMAGE_CAP, 'Remove Damage Cap')
        ]
        for key in seed_modifier_keys:
            if self.settings.get(key[0]):
                seed_modifiers.append(key[1])
        if self.settings.get(settingkey.ABILITY_POOL) == 'randomize':
            seed_modifiers.append('Randomize Ability Pool')

        # spoilerLog
        session["spoilerLog"] = makeSpoilerLog

        # hintsType/reportDepth/preventSelfHinting/allowProofHinting
        session['hintsType'] = self.settings.get(settingkey.HINT_SYSTEM)
        session['reportDepth'] = self.settings.get(settingkey.REPORT_DEPTH)
        session['preventSelfHinting'] = self.settings.get(settingkey.PREVENT_SELF_HINTING)
        session['allowProofHinting'] = self.settings.get(settingkey.ALLOW_PROOF_HINTING)

        # promiseCharm
        session['promiseCharm'] = self.settings.get(settingkey.ENABLE_PROMISE_CHARM)

        # keybladeAbilities
        keyblade_abilities = []
        session['keybladeAbilities'] = keyblade_abilities
        if self.settings.get(settingkey.SUPPORT_KEYBLADE_ABILITIES):
            keyblade_abilities.append('Support')
        if self.settings.get(settingkey.ACTION_KEYBLADE_ABILITIES):
            keyblade_abilities.append('Action')

        # keybladeMinStat
        session['keybladeMinStat'] = self.settings.get(settingkey.KEYBLADE_MIN_STAT)

        # keybladeMaxStat
        session['keybladeMaxStat'] = self.settings.get(settingkey.KEYBLADE_MAX_STAT)

        # soraExpMult
        session['soraExpMult'] = self.settings.get(settingkey.SORA_EXP_MULTIPLIER)

        # formExpMult
        session['formExpMult'] = {
            '0': self.settings.get(settingkey.SUMMON_EXP_MULTIPLIER),
            '1': self.settings.get(settingkey.VALOR_EXP_MULTIPLIER),
            '2': self.settings.get(settingkey.WISDOM_EXP_MULTIPLIER),
            '3': self.settings.get(settingkey.LIMIT_EXP_MULTIPLIER),
            '4': self.settings.get(settingkey.MASTER_EXP_MULTIPLIER),
            '5': self.settings.get(settingkey.FINAL_EXP_MULTIPLIER)
        }

        # enemyOptions
        enemy_options = {
            'remove_damage_cap': self.settings.get(settingkey.REMOVE_DAMAGE_CAP)
        }
        for setting in seedSettings.boss_enemy_settings:
            value = self.settings.get(setting.name)
            if value is not None:
                enemy_options[setting.name] = value
        session['enemyOptions'] = json.dumps(enemy_options)

        # for key in sorted(session.keys()):
        #     print(str(key) + ' : ' + str(session[key]))

        return session

    def makeSeed(self,platform):
        data = {
            'platform': platform,
            'cmdMenuChoice': self.settings.get(settingkey.COMMAND_MENU),
            'randomBGM': self.settings.get(settingkey.BGM_OPTIONS) + self.settings.get(settingkey.BGM_GAMES)
        }

        session = self.make_seed_session()

        self.genSeed(data,session)

    def downloadSeed(self):
        saveFileWidget = QFileDialog()
        saveFileWidget.setNameFilters(["Zip Seed File (*.zip)"])
        outfile_name,_ = saveFileWidget.getSaveFileName(self,"Save seed zip","randoseed.zip","Zip Seed File (*.zip)")
        if outfile_name!="":
            if not outfile_name.endswith(".zip"):
                outfile_name+=".zip"
            open(outfile_name, "wb").write(self.zip_file.getbuffer())
        self.zip_file=None

    def handleResult(self,result):
        self.progress.close()
        self.zip_file = result
        self.downloadSeed()

    def genSeed(self,data,session):
        self.thread = QThread()
        displayedSeedName = session["seed"]
        self.progress = QProgressDialog(f"Creating seed with name {displayedSeedName}","",0,0,None)
        self.progress.setWindowTitle("Making your Seed, please wait...")
        self.progress.setCancelButton(None)
        self.progress.setModal(True)
        self.progress.show()

        self.thread = GenSeedThread()
        self.thread.provideData(data,session)
        self.thread.finished.connect(self.handleResult)
        self.thread.start()

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

    def shareSeed(self):
        # if seed hasn't been set yet, make one
        current_seed = self.seedName.text()
        if current_seed == "":
            current_seed = self.random_seed_name()
            self.seedName.setText(current_seed)

        shared_seed = SharedSeed(
            generator_version=LOCAL_UI_VERSION,
            seed_name=current_seed,
            spoiler_log=self.spoiler_log.isChecked(),
            settings_string=self.settings.settings_string()
        )
        output_text = shared_seed.to_share_string()

        pc.copy(output_text)
        message = QMessageBox(text="Copied seed to clipboard")
        message.setWindowTitle("KH2 Seed Generator")
        message.exec()

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

        self.seedName.setText(shared_seed.seed_name)
        self.spoiler_log.setCheckState(Qt.Checked if shared_seed.spoiler_log else Qt.Unchecked)
        self.settings.apply_settings_string(shared_seed.settings_string)
        for widget in self.widgets:
            widget.update_widgets()
        message = QMessageBox(text="Received seed from clipboard")
        message.setWindowTitle("KH2 Seed Generator")
        message.exec()

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
