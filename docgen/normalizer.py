"""Step 3: turn a validated spec into a tidy, predictable shape.

The renderer can then trust every field: optional fields always exist,
methods are uppercase, and responses are sorted by status code.
Unknown fields are dropped here, which is how they get "ignored".

Only call this on a spec that passed validate_spec(). The input is
never changed; a new dict is returned.
"""


def normalize_spec(spec):
    return {
        "name": spec["name"].strip(),
        "version": spec["version"].strip(),
        "description": spec.get("description", "").strip(),
        "base_url": spec["base_url"].strip(),
        # Endpoints keep the author's order.
        "endpoints": [_normalize_endpoint(e) for e in spec["endpoints"]],
    }


def _normalize_endpoint(endpoint):
    responses = [_normalize_response(r) for r in endpoint["responses"]]
    return {
        "method": endpoint["method"].upper(),
        "path": endpoint["path"].strip(),
        "summary": endpoint["summary"].strip(),
        "description": endpoint.get("description", "").strip(),
        # Parameters keep the author's order.
        "parameters": [_normalize_parameter(p) for p in endpoint.get("parameters", [])],
        # Responses are always shown lowest status first.
        "responses": sorted(responses, key=lambda r: r["status"]),
    }


def _normalize_parameter(parameter):
    return {
        "name": parameter["name"].strip(),
        "in": parameter["in"],
        "type": parameter["type"],
        "required": parameter.get("required", False),
        "description": parameter.get("description", "").strip(),
        # Like response examples, an example can legitimately be null.
        "has_example": "example" in parameter,
        "example": parameter.get("example"),
    }


def _normalize_response(response):
    return {
        "status": response["status"],
        "description": response["description"].strip(),
        # An example can legitimately be null, so record presence separately.
        "has_example": "example" in response,
        "example": response.get("example"),
    }
