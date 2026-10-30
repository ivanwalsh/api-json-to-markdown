"""Convert an OpenAPI 3 document into docgen's own spec format.

The loader has already turned the file into Python data. If that data
is an OpenAPI document, from_openapi() reshapes it into the simple format
the rest of the pipeline understands. After that, the validator, checker
and renderer work exactly as they do for a hand-written spec.

What maps to what:
    info.title, info.version, info.description   name, version, description
    first entry in servers                       base_url
    each path + method in paths                  one endpoint, in file order
    summary (or operationId if missing)          summary
    description                                  description
    first entry in tags                          tag
    parameters (path, query, header)             parameters
    properties of a JSON requestBody             body parameters
    responses with a numeric status code         responses
    $ref pointers such as #/components/...       followed and filled in

Known limits, skipped quietly for now:
    cookie parameters, HEAD/OPTIONS/TRACE methods, "default" and "2XX"
    style responses, non-JSON request and response bodies, and $ref
    pointers to other files.
"""

from .errors import SpecError

METHODS = ("get", "post", "put", "patch", "delete")
PARAMETER_LOCATIONS = ("path", "query", "header")
MAX_REF_DEPTH = 20

# A unique marker meaning "no example given". We can't use None for this,
# because null is a legitimate example value.
MISSING = object()


def is_openapi(data):
    """True if the parsed file looks like OpenAPI or Swagger, not our own format."""
    return isinstance(data, dict) and ("openapi" in data or "swagger" in data)


def prepare_spec(data):
    """Convert OpenAPI data to our format; pass our own format through unchanged."""
    return from_openapi(data) if is_openapi(data) else data


def from_openapi(document):
    """Return a spec in docgen's own format, built from an OpenAPI 3 document."""
    if "swagger" in document:
        raise SpecError(
            "This is a Swagger 2.0 file, which is not supported yet. "
            "Convert it to OpenAPI 3 first."
        )
    version = str(document.get("openapi", ""))
    if not version.startswith("3."):
        raise SpecError(f'openapi: version "{version}" is not supported (use 3.0 or 3.1)')

    spec = _convert_info(document)
    spec["endpoints"] = _convert_paths(document, _as_dict(document.get("paths")))
    return spec


def _convert_info(document):                      
    """Map info and servers to name, version, description, and base url"""
    info = document.get("info", {})
    servers = document.get("servers", [{}])   
    return {
        "name": info.get("title", ""),
        "version": info.get("version", ""),
        "description": info.get("description", ""),
        "base_url": servers[0].get("url", ""),
    } 


# --- Endpoints ---------------------------------------------------------------


def _convert_paths(document, paths):
    endpoints = []
    for path, path_item in paths.items():
        path_item = _as_dict(_resolve(document, path_item))
        # Parameters listed on the path apply to every method under it.
        shared = path_item.get("parameters") or []
        for method, operation in path_item.items():
            if method in METHODS:
                endpoints.append(_convert_operation(document, method, path, operation, shared))
    return endpoints


def _convert_operation(document, method, path, operation, shared_parameters):
    operation = _as_dict(_resolve(document, operation))
    endpoint = {
        "method": method.upper(),
        "path": path,
        # Our format needs a summary. Fall back to operationId, a short name
        # many specs have. If both are missing, the validator says which
        # endpoint needs one.
        "summary": operation.get("summary") or operation.get("operationId", ""),
        "responses": _convert_responses(document, _as_dict(operation.get("responses"))),
    }
    if operation.get("description"):
        endpoint["description"] = operation["description"]
    tags = operation.get("tags") or []
    if tags:
        endpoint["tag"] = tags[0]

    parameters = _merge_parameters(document, shared_parameters, operation.get("parameters") or [])
    parameters += _body_parameters(document, operation.get("requestBody"))
    if parameters:
        endpoint["parameters"] = parameters
    return endpoint


def _merge_parameters(document, shared, own):
    """Combine path-level and operation-level parameters.

    If both define the same name and location, the operation's version
    wins but keeps the position of the first one.
    """
    merged = {}
    for raw in list(shared) + list(own):
        parameter = _as_dict(_resolve(document, raw))
        if parameter.get("in") in PARAMETER_LOCATIONS:  # skips cookie parameters
            merged[(parameter.get("name"), parameter.get("in"))] = parameter
    return [_convert_parameter(document, p) for p in merged.values()]


def _convert_parameter(document, parameter):
    schema = _as_dict(_resolve(document, parameter.get("schema")))
    converted = {
        "name": parameter.get("name"),
        "in": parameter.get("in"),
        "type": _schema_type(schema),
        "required": parameter.get("required", False),
    }
    if parameter.get("description"):
        converted["description"] = parameter["description"]
    example = _first_example(document, parameter, schema)
    if example is not MISSING:
        converted["example"] = example
    return converted


def _body_parameters(document, request_body):
    """Turn each property of a JSON request body into a body parameter."""
    body = _as_dict(_resolve(document, request_body))
    media = _as_dict(_as_dict(body.get("content")).get("application/json"))
    schema = _as_dict(_resolve(document, media.get("schema")))
    body_example = _first_example(document, media, {})
    required = schema.get("required") or []

    parameters = []
    for name, prop in _as_dict(schema.get("properties")).items():
        prop = _as_dict(_resolve(document, prop))
        converted = {
            "name": name,
            "in": "body",
            "type": _schema_type(prop),
            "required": name in required,
        }
        if prop.get("description"):
            converted["description"] = prop["description"]
        example = _first_example(document, prop, prop)
        # No example on the property itself? Borrow it from a whole-body example.
        if example is MISSING and isinstance(body_example, dict) and name in body_example:
            example = body_example[name]
        if example is not MISSING:
            converted["example"] = example
        parameters.append(converted)
    return parameters


def _convert_responses(document, responses):
    converted = []
    for code, response in responses.items():
        code = str(code)
        if not (len(code) == 3 and code.isdigit()):
            continue  # skips "default" and ranges like "2XX"
        response = _as_dict(_resolve(document, response))
        item = {"status": int(code), "description": response.get("description", "")}
        media = _as_dict(_as_dict(response.get("content")).get("application/json"))
        schema = _as_dict(_resolve(document, media.get("schema")))
        example = _first_example(document, media, schema)
        if example is not MISSING:
            item["example"] = example
        converted.append(item)
    return converted


# --- Small helpers -----------------------------------------------------------


def _resolve(document, value):
    """Follow $ref pointers like "#/components/schemas/Book" to what they point at."""
    depth = 0
    while isinstance(value, dict) and "$ref" in value:
        ref = value["$ref"]
        depth += 1
        if depth > MAX_REF_DEPTH:
            raise SpecError(f"{ref}: too many nested $ref pointers (is one circular?)")
        if not isinstance(ref, str) or not ref.startswith("#/"):
            raise SpecError(f'{ref}: only references inside the same file ("#/...") are supported')
        target = document
        for part in ref[2:].split("/"):
            # JSON Pointer escapes: ~1 means "/" and ~0 means "~".
            part = part.replace("~1", "/").replace("~0", "~")
            if not isinstance(target, dict) or part not in target:
                raise SpecError(f"{ref}: reference not found")
            target = target[part]
        value = target
    return value


def _first_example(document, holder, schema):
    """Find an example: holder.example, then holder.examples, then the schema's."""
    if "example" in holder:
        return holder["example"]
    examples = holder.get("examples")
    if isinstance(examples, dict) and examples:
        first = _as_dict(_resolve(document, next(iter(examples.values()))))
        if "value" in first:
            return first["value"]
    if "example" in schema:
        return schema["example"]
    # OpenAPI 3.1 schemas use a list called "examples".
    if isinstance(schema.get("examples"), list) and schema["examples"]:
        return schema["examples"][0]
    return MISSING


def _schema_type(schema):
    """Pick a type name docgen understands from an OpenAPI schema."""
    kind = schema.get("type")
    if isinstance(kind, list):  # OpenAPI 3.1 allows ["string", "null"]
        kind = next((k for k in kind if k != "null"), None)
    if kind:
        return kind
    if "properties" in schema:
        return "object"
    if "items" in schema:
        return "array"
    return "string"


def _as_dict(value):
    """Treat anything that isn't a dictionary as an empty one, so .get() is safe."""
    return value if isinstance(value, dict) else {}
