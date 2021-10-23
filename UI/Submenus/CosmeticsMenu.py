from Class import settingkey
from Class.seedSettings import SeedSettings
from UI.Submenus.SubMenu import KH2Submenu


class CosmeticsMenu(KH2Submenu):

    def __init__(self, settings: SeedSettings, enabled: bool = True):
        super().__init__(title='Cosmetics', settings=settings, enabled=enabled)

        self.add_option(settingkey.COMMAND_MENU)
        self.add_option(settingkey.BGM_OPTIONS)
        self.add_option(settingkey.BGM_GAMES)

        self.finalizeMenu()
