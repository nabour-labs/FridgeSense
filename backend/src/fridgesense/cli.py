"""Command-line tools. Run with the AWS profile from .env loaded."""

from fridgesense import deps
from fridgesense.devices import DeviceRepository, discover
from fridgesense.store import TokenStore


def devices_main() -> int:
    """Refresh and print the linked Ring account's devices."""
    tokens = TokenStore().load()
    if tokens is None:
        print("No Ring account is linked. Link it from the Ring app first.")
        return 1
    devices = discover(deps.ring_client(), DeviceRepository(), tokens.account_id)
    if devices is None:
        print("Could not load devices from Ring. Check the logs and try again.")
        return 1
    for d in devices:
        print(f"{d.device_id}  {d.name}")
    return 0
