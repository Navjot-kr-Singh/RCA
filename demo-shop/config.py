"""Service config per release, with a typo in release v2.

Lets the demo hit a realistic bad-deploy error: the app can't read a setting
right after a release, and rolling back fixes it.
"""

RELEASES = {
    "v1": {"payment_timeout_ms": 3000, "currency": "USD", "max_items": 20},
    # The typo ships here: "paymnet" instead of "payment".
    "v2": {"paymnet_timeout_ms": 3000, "currency": "USD", "max_items": 20},
}


class ConfigError(Exception):
    """Raised when the current release's config is missing a setting."""


class ServiceConfig:
    def __init__(self, release="v1"):
        self.deploy(release)

    def deploy(self, version):
        """Switch to another release, like a deploy or a rollback."""
        if version not in RELEASES:
            raise ValueError(f"release must be one of {tuple(RELEASES)}")
        self.current_release = version

    def get_setting(self, name):
        settings = RELEASES[self.current_release]
        if name not in settings:
            # Worded with "deploy" so the RCA demo mode matches this scenario.
            raise ConfigError(
                f"config error in release {self.current_release} after deploy: "
                f"missing setting {name} (typo in service config?)"
            )
        return settings[name]

    def ok(self):
        try:
            self.get_setting("payment_timeout_ms")
        except ConfigError:
            return False
        return True
