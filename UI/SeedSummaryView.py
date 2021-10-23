import json
import random
from pathlib import Path

import pyperclip as pc
from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QLabel, QPushButton, QTabWidget, QVBoxLayout, QHBoxLayout, QWidget, QFileDialog,
    QProgressDialog, QDialog, QMessageBox, QLineEdit, QGridLayout
)

from Class import seedSettings, settingkey
from Class.seedSettings import SeedSettings
from List.configDict import locationType
from List.hashTextEntries import generateHashIcons
from Module.randomizePage import randomizePage
from Module.resources import resource_path
from Module.seedshare import SharedSeed
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


class GenSeedThread(QThread):
    finished = Signal(object)

    def provideData(self,data,session):
        self.data=data
        self.session = session
        self.zip_file = None

    def run(self):
        zip_file = randomizePage(self.data,self.session,local_ui=True)
        self.finished.emit(zip_file)


class SeedSummaryView(QDialog):

    def __init__(
            self,
            parent: QWidget,
            local_ui_version: str,
            seed_name: str,
            settings: SeedSettings,
            spoiler_log: bool
    ):
        super().__init__(parent)

        self.local_ui_version = local_ui_version
        self.seed_name = seed_name
        self.settings = settings
        self.spoiler_log = spoiler_log

        self.setWindowTitle("Seed Summary")
        self.setWindowIcon(QIcon(resource_path("Module/icon.png")))
        self.setMinimumWidth(1000)

        pagelayout = QVBoxLayout()
        seed_layout = QHBoxLayout()
        submit_layout = QHBoxLayout()
        self.tabs = QTabWidget()

        pagelayout.addLayout(seed_layout)
        pagelayout.addWidget(self.tabs)
        pagelayout.addLayout(submit_layout)

        summary_section = QGridLayout()
        summary_section.addWidget(QLabel('Seed'), 0, 0)
        seed_name_widget = QLineEdit(seed_name)
        seed_name_widget.setEnabled(False)
        summary_section.addWidget(seed_name_widget, 0, 1)

        summary_section.addWidget(QLabel('Spoiler Log'), 1, 0)
        spoiler_log_widget = QLineEdit('Enabled' if spoiler_log else 'Disabled')
        spoiler_log_widget.setEnabled(False)
        summary_section.addWidget(spoiler_log_widget, 1, 1)

        summary_section.addWidget(QLabel("Seed Hash"), 2, 0)
        seedhashlayout = QHBoxLayout()
        self.hashIconPath = Path(resource_path("static/seed-hash-icons"))
        self.hashIcons = []
        for i in range(7):
            self.hashIcons.append(QLabel())
            self.hashIcons[-1].blockSignals(True)
            #self.hashIcons[-1].setIconSize(QSize(50,50))
            self.hashIcons[-1].setPixmap(QPixmap(str(self.hashIconPath.absolute())+"/"+"question-mark.png"))
            seedhashlayout.addWidget(self.hashIcons[-1])
        seedhashlayout.addStretch()
        summary_section.addLayout(seedhashlayout, 2, 1)

        seed_layout.addLayout(summary_section)

        self.widgets = [
            CosmeticsMenu(self.settings, enabled=True),
            SoraMenu(self.settings, enabled=False),
            StartingMenu(self.settings, enabled=False),
            HintsMenu(self.settings, enabled=False),
            KeybladeMenu(self.settings, enabled=False),
            WorldMenu(self.settings, enabled=False),
            MiscMenu(self.settings, enabled=False),
            SeedModMenu(self.settings, enabled=False),
            ItemPlacementMenu(self.settings, enabled=False),
            BossEnemyMenu(self.settings, enabled=False)
        ]

        for i in range(len(self.widgets)):
            self.tabs.addTab(self.widgets[i],self.widgets[i].getName())

        submit_emu = QPushButton("Generate Seed (PCSX2)")
        submit_emu.clicked.connect(lambda: self.makeSeed("PCSX2"))
        submit_layout.addWidget(submit_emu)

        submit_pc = QPushButton("Generate Seed (PC)")
        submit_pc.clicked.connect(lambda: self.makeSeed("PC"))
        submit_layout.addWidget(submit_pc)

        share = QPushButton("Share Seed")
        share.clicked.connect(self.shareSeed)
        submit_layout.addWidget(share)

        self.setLayout(pagelayout)

        self.session = self.make_seed_session()

    def closeEvent(self, e):
        # Pass along the private settings that may have been adjusted on this view
        self.parent().settings.apply_private_settings(self.settings)
        e.accept()

    def make_seed_session(self):
        session={}

        # seed
        session["seed"] = self.seed_name

        # make seed hash dependent on ui version, if a spoiler log is generated or not, and the public seed settings
        settings_string = self.settings.settings_string(include_private=False)
        random.seed(session["seed"] + self.local_ui_version + str(self.spoiler_log) + settings_string)

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

        # update the seed hash display
        for index, icon in enumerate(session['seedHashIcons']):
            self.hashIcons[index].setPixmap(QPixmap(str(self.hashIconPath.absolute()) + '/' + icon + '.png'))

        # spoilerLog
        session["spoilerLog"] = self.spoiler_log

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
            'randomBGM': {
                "options": self.settings.get(settingkey.BGM_OPTIONS),
                "games": self.settings.get(settingkey.BGM_GAMES)
            }
        }

        self.genSeed(data, self.session)

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
        self.progress = QProgressDialog('Generating seed...', '', 0, 0, self)
        self.progress.setWindowTitle('KH2 Seed Generator')
        self.progress.setCancelButton(None)
        self.progress.setModal(True)
        self.progress.show()

        self.thread = GenSeedThread()
        self.thread.provideData(data,session)
        self.thread.finished.connect(self.handleResult)
        self.thread.start()

    def shareSeed(self):
        shared_seed = SharedSeed(
            generator_version=self.local_ui_version,
            seed_name=self.seed_name,
            spoiler_log=self.spoiler_log,
            settings_string=self.settings.settings_string()
        )
        output_text = shared_seed.to_share_string()

        pc.copy(output_text)
        message = QMessageBox(text="Copied seed to clipboard")
        message.setWindowTitle("KH2 Seed Generator")
        message.exec()
