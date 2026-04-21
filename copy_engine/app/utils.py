from flask import request


def wants_json() -> bool:
    acc = request.headers.get("Accept", "")
    if "application/json" in acc:
        return True
    if request.args.get("format") == "json":
        return True
    return bool(request.is_json and request.mimetype == "application/json")
