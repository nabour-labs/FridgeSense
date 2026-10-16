"""The single DynamoDB table, with plain Python values in and out (no Decimal)."""

from decimal import Decimal
from typing import Any

import boto3
from boto3.dynamodb.types import TypeDeserializer, TypeSerializer
from botocore.exceptions import ClientError

from fridgesense.store import table_name

_ser = TypeSerializer()
_de = TypeDeserializer()


def account_pk(account_id: str) -> str:
    return f"ACCOUNT#{account_id}"


def _to_dynamo(value: Any) -> Any:
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, dict):
        return {k: _to_dynamo(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_to_dynamo(v) for v in value]
    return value


def _from_dynamo(value: Any) -> Any:
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, dict):
        return {k: _from_dynamo(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_from_dynamo(v) for v in value]
    return value


def serialize(item: dict) -> dict:
    return {k: _ser.serialize(_to_dynamo(v)) for k, v in item.items()}


def deserialize(item: dict) -> dict:
    return _from_dynamo({k: _de.deserialize(v) for k, v in item.items()})


class TransactionConflict(Exception):
    """A transaction was cancelled; `reasons` holds one code per item ("None" if fine)."""

    def __init__(self, reasons: list[str]):
        super().__init__(", ".join(reasons))
        self.reasons = reasons


class FridgeTable:
    def __init__(self, name: str | None = None):
        self.name = name or table_name()
        self.client = boto3.client("dynamodb")

    def get(self, pk: str, sk: str) -> dict | None:
        resp = self.client.get_item(TableName=self.name, Key=serialize({"pk": pk, "sk": sk}))
        return deserialize(resp["Item"]) if "Item" in resp else None

    def query(self, account_id: str, prefix: str) -> list[dict]:
        items, start = [], None
        while True:
            kwargs = {
                "TableName": self.name,
                "KeyConditionExpression": "pk = :pk AND begins_with(sk, :prefix)",
                "ExpressionAttributeValues": serialize(
                    {":pk": account_pk(account_id), ":prefix": prefix}
                ),
            }
            if start:
                kwargs["ExclusiveStartKey"] = start
            resp = self.client.query(**kwargs)
            items += [deserialize(i) for i in resp["Items"]]
            start = resp.get("LastEvaluatedKey")
            if not start:
                return items

    def query_range(
        self,
        account_id: str,
        low: str,
        high: str,
        newest_first: bool = False,
        limit: int | None = None,
    ) -> list[dict]:
        """Items whose sort key is between `low` and `high` (inclusive)."""
        items, start = [], None
        while True:
            kwargs = {
                "TableName": self.name,
                "KeyConditionExpression": "pk = :pk AND sk BETWEEN :low AND :high",
                "ExpressionAttributeValues": serialize(
                    {":pk": account_pk(account_id), ":low": low, ":high": high}
                ),
                "ScanIndexForward": not newest_first,
            }
            if limit:
                kwargs["Limit"] = limit - len(items)
            if start:
                kwargs["ExclusiveStartKey"] = start
            resp = self.client.query(**kwargs)
            items += [deserialize(i) for i in resp["Items"]]
            start = resp.get("LastEvaluatedKey")
            if not start or (limit and len(items) >= limit):
                return items

    def put(self, item: dict) -> None:
        self.client.put_item(TableName=self.name, Item=serialize(item))

    def delete(self, pk: str, sk: str) -> bool:
        """Delete one item; False if it did not exist."""
        resp = self.client.delete_item(
            TableName=self.name, Key=serialize({"pk": pk, "sk": sk}), ReturnValues="ALL_OLD"
        )
        return "Attributes" in resp

    def update(self, pk: str, sk: str, values: dict) -> None:
        names = {f"#{i}": k for i, k in enumerate(values)}
        expr = ", ".join(f"#{i} = :{i}" for i in range(len(values)))
        self.client.update_item(
            TableName=self.name,
            Key=serialize({"pk": pk, "sk": sk}),
            UpdateExpression=f"SET {expr}",
            ExpressionAttributeNames=names,
            ExpressionAttributeValues=serialize(
                {f":{i}": v for i, v in enumerate(values.values())}
            ),
        )

    def append(self, pk: str, sk: str, field: str, values: list) -> None:
        """Atomically append to a list attribute (created empty)."""
        self.client.update_item(
            TableName=self.name,
            Key=serialize({"pk": pk, "sk": sk}),
            UpdateExpression="SET #f = list_append(if_not_exists(#f, :empty), :v)",
            ExpressionAttributeNames={"#f": field},
            ExpressionAttributeValues=serialize({":empty": [], ":v": values}),
        )

    def add(self, pk: str, sk: str, field: str, amount: float) -> None:
        """Atomically add `amount` to a number attribute (created at 0)."""
        self.client.update_item(
            TableName=self.name,
            Key=serialize({"pk": pk, "sk": sk}),
            UpdateExpression="ADD #f :a",
            ExpressionAttributeNames={"#f": field},
            ExpressionAttributeValues=serialize({":a": amount}),
        )

    def add_many(self, pk: str, sk: str, amounts: dict[str, float]) -> None:
        """Atomically add each amount to its number attribute (created at 0), in one update."""
        names = {f"#f{i}": field for i, field in enumerate(amounts)}
        values = {f":a{i}": amount for i, amount in enumerate(amounts.values())}
        self.client.update_item(
            TableName=self.name,
            Key=serialize({"pk": pk, "sk": sk}),
            UpdateExpression="ADD " + ", ".join(f"#f{i} :a{i}" for i in range(len(amounts))),
            ExpressionAttributeNames=names,
            ExpressionAttributeValues=serialize(values),
        )

    def increment_below(self, pk: str, sk: str, field: str, limit: int) -> bool:
        """Atomically add 1 to a counter (created at 0) unless it has reached `limit`."""
        try:
            self.client.update_item(
                TableName=self.name,
                Key=serialize({"pk": pk, "sk": sk}),
                UpdateExpression="ADD #f :one",
                ConditionExpression="attribute_not_exists(#f) OR #f < :limit",
                ExpressionAttributeNames={"#f": field},
                ExpressionAttributeValues=serialize({":one": 1, ":limit": limit}),
            )
        except self.client.exceptions.ConditionalCheckFailedException:
            return False
        return True

    def transact(self, items: list[dict]) -> None:
        """Write items atomically. Each entry is {"Put": {...}} or {"Update": {...}} with
        plain values; TableName and serialization are filled in here."""
        prepared = []
        for entry in items:
            ((op, spec),) = entry.items()
            spec = {**spec, "TableName": self.name}
            if "Item" in spec:
                spec["Item"] = serialize(spec["Item"])
            if "Key" in spec:
                spec["Key"] = serialize(spec["Key"])
            if "ExpressionAttributeValues" in spec:
                spec["ExpressionAttributeValues"] = serialize(spec["ExpressionAttributeValues"])
            prepared.append({op: spec})
        try:
            self.client.transact_write_items(TransactItems=prepared)
        except ClientError as e:
            if e.response["Error"]["Code"] != "TransactionCanceledException":
                raise
            reasons = [r.get("Code", "None") for r in e.response.get("CancellationReasons", [])]
            raise TransactionConflict(reasons) from None
