def success_response(message, code, data=None, status_code=200):
    return {
        "success": True,
        "code": code,
        "message": message,
        "data": data,
        "errors": None
    }

