"""Ring devices of the linked account, stored in the single table."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

import boto3
import httpx
from boto3.dynamodb.conditions import Key

from fridgesense.logs import log_event
from fridgesense.oauth import OAuthRejected, OAuthUnavailable
from fridgesense.ring import RingAuthError, RingClient
from fridgesense.store import table_name as table_name_default
from fridgesense.table import account_pk


@dataclass(frozen=True)
class Device:
    device_id: str
    name: str


class DeviceRepository:
    def __init__(self, table_name: str | None = None):
        self.table = boto3.resource("dynamodb").Table(table_name or table_name_default())

    def list(self, account_id: str) -> list[Device]:
        resp = self.table.query(
            KeyConditionExpression=Key("pk").eq(account_pk(account_id))
            & Key("sk").begins_with("DEVICE#")
        )
        return [Device(i["sk"].removeprefix("DEVICE#"), i["name"]) for i in resp["Items"]]

    def replace(self, account_id: str, devices: list[Device]) -> None:
        keep = {d.device_id for d in devices}
        pk = account_pk(account_id)
        now = int(time.time())
        with self.table.batch_writer() as batch:
            for old in self.list(account_id):
                if old.device_id not in keep:
                    batch.delete_item(Key={"pk": pk, "sk": f"DEVICE#{old.device_id}"})
            for d in devices:
                item = {"pk": pk, "sk": f"DEVICE#{d.device_id}", "name": d.name}
                batch.put_item(Item={**item, "updated_at": now})


def fetch_devices(ring: RingClient) -> list[Device] | None:
    """The account's devices from Ring, or None if Ring could not be reached."""
    try:
        resp = ring.get("/v1/devices")
    except (httpx.HTTPError, RingAuthError, OAuthRejected, OAuthUnavailable) as e:
        log_event("devices_unavailable", logging.WARNING, error=type(e).__name__)
        return None
    if resp.status_code != 200:
        log_event("devices_unavailable", logging.WARNING, status=resp.status_code)
        return None
    return [
        Device(d["id"], d.get("attributes", {}).get("name", d["id"])) for d in resp.json()["data"]
    ]


def discover(ring: RingClient, repo: DeviceRepository, account_id: str) -> list[Device] | None:
    """Fetch and store the account's devices; leaves the stored list alone on failure."""
    devices = fetch_devices(ring)
    if devices is not None:
        repo.replace(account_id, devices)
        log_event("devices_saved", account_id=account_id, count=len(devices))
    return devices
