from rest_framework.views import exception_handler

def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)

    if response is not None:
        response.data = {
            "code": getattr(exc, "code", "ERROR"),
            "message": response.data.get("detail", str(exc))
        }

    return response