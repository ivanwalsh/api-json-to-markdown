"""Step 2: check parsed JSON against the spec schema.

The validator collects every problem it finds and raises one SpecError
holding all of them. Each message starts with the location of the
problem, for example `endpoints[1].method`, so it is easy to find in
the JSON file.

Unknown fields are ignored on purpose (the "forgiving" choice).
"""

from .errors import SpecError

METHODS = ("GET", "POST", "PUT", "PATCH", "DELETE")
LOCATIONS = ("path", "query", "header", "body")
TYPES = ("string", "integer", "number", "boolean", "array", "object")


def validate_spec(spec):
    """Raise SpecError if `spec` breaks any schema rule. Return None if valid."""
    if not isinstance(spec, dict):
        raise SpecError(
            f"The top level must be a JSON object, got {_json_type(spec)}"
        )

    errors = []
    _check_string(spec, "name", "name", errors, required=True)
    _check_string(spec, "version", "version", errors, required=True)
    _check_string(spec, "description", "description", errors, required=False)

    base_url = _check_string(spec, "base_url", "base_url", errors, required=True)
    if base_url is not None and not base_url.startswith(("http://", "https://")):
        errors.append("base_url: must start with http:// or https://")

    endpoints = _check_list(spec, "endpoints", "endpoints", errors, required=True)
    if endpoints is not None:
        if not endpoints:
            errors.append("endpoints: must contain at least one endpoint")
        seen = {}
        for index, endpoint in enumerate(endpoints):
            where = f"endpoints[{index}]"
            key = _check_endpoint(endpoint, where, errors)
            if key is None:
                continue
            if key in seen:
                errors.append(
                    f"{where}: duplicate endpoint {key[0]} {key[1]} "
                    f"(already defined at endpoints[{seen[key]}])"
                )
            else:
                seen[key] = index

    if errors:
        raise SpecError(errors)


def _check_endpoint(endpoint, where, errors):
    """Check one endpoint. Return (METHOD, path) if both are usable, else None."""
    if not isinstance(endpoint, dict):
        errors.append(f"{where}: must be an object, got {_json_type(endpoint)}")
        return None

    method = _check_string(endpoint, "method", f"{where}.method", errors, required=True)
    if method is not None and method.upper() not in METHODS:
        errors.append(
            f'{where}.method: "{method}" is not a valid method '
            f"(use one of {', '.join(METHODS)})"
        )
        method = None

    path = _check_string(endpoint, "path", f"{where}.path", errors, required=True)
    if path is not None and not path.startswith("/"):
        errors.append(f'{where}.path: must start with "/"')
        path = None

    _check_string(endpoint, "summary", f"{where}.summary", errors, required=True)
    _check_string(endpoint, "description", f"{where}.description", errors, required=False)

    parameters = _check_list(
        endpoint, "parameters", f"{where}.parameters", errors, required=False
    )
    if parameters is not None:
        names = set()
        for index, parameter in enumerate(parameters):
            name = _check_parameter(parameter, f"{where}.parameters[{index}]", errors)
            if name is None:
                continue
            if name in names:
                errors.append(
                    f'{where}.parameters[{index}].name: duplicate parameter "{name}"'
                )
            names.add(name)

    responses = _check_list(
        endpoint, "responses", f"{where}.responses", errors, required=True
    )
    if responses is not None:
        if not responses:
            errors.append(f"{where}.responses: must contain at least one response")
        statuses = set()
        for index, response in enumerate(responses):
            status = _check_response(response, f"{where}.responses[{index}]", errors)
            if status is None:
                continue
            if status in statuses:
                errors.append(
                    f"{where}.responses[{index}].status: duplicate status {status}"
                )
            statuses.add(status)

    if method is None or path is None:
        return None
    return (method.upper(), path)


def _check_parameter(parameter, where, errors):
    """Check one parameter. Return its name if usable, else None."""
    if not isinstance(parameter, dict):
        errors.append(f"{where}: must be an object, got {_json_type(parameter)}")
        return None

    name = _check_string(parameter, "name", f"{where}.name", errors, required=True)
    _check_choice(parameter, "in", f"{where}.in", LOCATIONS, errors)
    _check_choice(parameter, "type", f"{where}.type", TYPES, errors)
    _check_string(parameter, "description", f"{where}.description", errors, required=False)

    if "required" in parameter and not isinstance(parameter["required"], bool):
        errors.append(
            f"{where}.required: must be true or false, "
            f"got {_json_type(parameter['required'])}"
        )
    return name


def _check_response(response, where, errors):
    """Check one response. Return its status code if usable, else None."""
    if not isinstance(response, dict):
        errors.append(f"{where}: must be an object, got {_json_type(response)}")
        return None

    _check_string(response, "description", f"{where}.description", errors, required=True)
    # "example" may hold any JSON value, so there is nothing to check.

    if "status" not in response:
        errors.append(f"{where}.status: required field is missing")
        return None
    status = response["status"]
    # bool is a kind of int in Python, so rule it out explicitly.
    if isinstance(status, bool) or not isinstance(status, int):
        errors.append(f"{where}.status: must be an integer, got {_json_type(status)}")
        return None
    if not 100 <= status <= 599:
        errors.append(f"{where}.status: must be between 100 and 599, got {status}")
        return None
    return status


# --- Small reusable helpers -------------------------------------------------


def _check_string(container, key, where, errors, required):
    """Check that `container[key]` is a string. Return it, or None on failure."""
    if key not in container:
        if required:
            errors.append(f"{where}: required field is missing")
        return None
    value = container[key]
    if not isinstance(value, str):
        errors.append(f"{where}: must be a string, got {_json_type(value)}")
        return None
    if required and not value.strip():
        errors.append(f"{where}: must not be empty")
        return None
    return value


def _check_list(container, key, where, errors, required):
    """Check that `container[key]` is a list. Return it, or None on failure."""
    if key not in container:
        if required:
            errors.append(f"{where}: required field is missing")
        return None
    value = container[key]
    if not isinstance(value, list):
        errors.append(f"{where}: must be a list, got {_json_type(value)}")
        return None
    return value


def _check_choice(container, key, where, allowed, errors):
    """Check that `container[key]` is one of the `allowed` strings."""
    value = _check_string(container, key, where, errors, required=True)
    if value is not None and value not in allowed:
        errors.append(
            f'{where}: "{value}" is not allowed (use one of {", ".join(allowed)})'
        )


def _json_type(value):
    """Describe a Python value using JSON's type names, for error messages."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return type(value).__name__
