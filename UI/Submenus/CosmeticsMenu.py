from Class import settingkey
from Class.seedSettings import SeedSettings
from UI.Submenus.SubMenu import KH2Submenu


class CosmeticsMenu(KH2Submenu):
    def __init__(self, settings: SeedSettings):
        super().__init__(title='Cosmetics', settings=settings)

        self.addHeader('Randomized Visuals')
        self.add_option(settingkey.COMMAND_MENU)

        self.addHeader('Randomized Music (PC Only)')
        self.add_option(settingkey.MUSIC_RANDO_MODE)
        self.add_option(settingkey.BGM_GAMES)
        self.add_option(settingkey.MUSIC_RANDO_EXCLUDE_DMCA_UNSAFE)
        self.add_option(settingkey.MUSIC_RANDO_ADD_CUSTOM_MUSIC)

        self.finalizeMenu()

        settings.observe(settingkey.MUSIC_RANDO_MODE, self._mode_changed)

    def _mode_changed(self):
        music_rando_on = self.settings.get(settingkey.MUSIC_RANDO_MODE) != 'off'
        self.set_option_visibility(settingkey.BGM_GAMES, visible=music_rando_on)
        self.set_option_visibility(settingkey.MUSIC_RANDO_EXCLUDE_DMCA_UNSAFE, visible=music_rando_on)
        self.set_option_visibility(settingkey.MUSIC_RANDO_ADD_CUSTOM_MUSIC, visible=music_rando_on)
