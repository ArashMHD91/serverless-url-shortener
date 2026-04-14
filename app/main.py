import json
import os
import random
import string
import boto3
from boto3.dynamodb.conditions import Key

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["DYNAMODB_TABLE"])

def generate_code(length=6):
    return "".join(random.choices(string.ascii_letters + string.digits, k=length))

def handler(event, context):
    method = event.get("requestContext", {}).get("http", {}).get("method", "")
    path = event.get("rawPath", "")

    # POST /shorten
    if method == "POST" and path == "/shorten":
        body = json.loads(event.get("body", "{}"))
        long_url = body.get("url")

        if not long_url:
            return {"statusCode": 400, "body": json.dumps({"error": "url is required"})}

        code = generate_code()
        table.put_item(Item={"code": code, "url": long_url})

        return {
            "statusCode": 201,
            "body": json.dumps({"short_code": code, "url": long_url})
        }

    # GET /{code}
    if method == "GET" and path != "/":
        code = path.lstrip("/")
        result = table.get_item(Key={"code": code})
        item = result.get("Item")

        if not item:
            return {"statusCode": 404, "body": json.dumps({"error": "not found"})}

        return {
            "statusCode": 301,
            "headers": {"Location": item["url"]},
            "body": ""
        }

    # DELETE /{code}
    if method == "DELETE":
        code = path.lstrip("/")
        table.delete_item(Key={"code": code})
        return {"statusCode": 200, "body": json.dumps({"message": "deleted"})}

    return {"statusCode": 400, "body": json.dumps({"error": "invalid request"})}