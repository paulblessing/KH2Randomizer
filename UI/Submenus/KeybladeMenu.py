from Class import settingkey
from Class.seedSettings import SeedSettings
from UI.Submenus.SubMenu import KH2Submenu


class KeybladeMenu(KH2Submenu):

    def __init__(self, settings: SeedSettings, enabled: bool = True):
        super().__init__(title='Keyblades', settings=settings, enabled=enabled)

        self.add_option(settingkey.KEYBLADE_MIN_STAT)
        self.add_option(settingkey.KEYBLADE_MAX_STAT)
        self.add_option(settingkey.SUPPORT_KEYBLADE_ABILITIES)
        self.add_option(settingkey.ACTION_KEYBLADE_ABILITIES)

        self.finalizeMenu()
