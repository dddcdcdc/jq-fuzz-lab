"""Reproducible byte, jq token, and JSON tree mutations."""
import json
import re

TOKEN = re.compile(rb'"(?:\\.|[^"\\])*"|[A-Za-z_][A-Za-z_0-9]*|\d+|[^\s]', re.DOTALL)
MAX_INPUT = 8192
MAX_MUTATION_ATTEMPTS = 100


def byte_mutation(data, rng):
    index = rng.randrange(len(data) + 1)
    op = rng.randrange(3)
    if op == 0 or index == len(data):
        return data[:index] + bytes([rng.randrange(256)]) + data[index:]
    if op == 1:
        return data[:index] + data[index + 1:]
    return data[:index] + bytes([data[index] ^ (1 << rng.randrange(8))]) + data[index + 1:]


def expression(rng, depth=0):
    leaf = rng.choice([".", ".name", ".items", "null", "1", '"hello"'])
    if depth == 2:
        return leaf
    part = expression(rng, depth + 1)
    return rng.choice([leaf, f"[{part}]", f"{{value: {part}}}", f"({part}) | type",
                       f"try ({part})", f"({part}) // {leaf}"])


def script_mutation(data, rng):
    tokens = list(TOKEN.finditer(data))
    if not tokens or rng.randrange(6) == 0:
        return (expression(rng) + "\n").encode("ascii")
    token = rng.choice(tokens)
    first, last = token.span()
    op = rng.randrange(5)
    if op == 0:
        return data[:last] + b"\n"
    if op == 1:
        return data[:first] + data[last:]
    if op == 2:
        insert = rng.choice([b"(", b")", b";", b",", b"|", b'"x"', b"[]"])
        return data[:last] + insert + data[last:]
    if op == 3:
        return data[:first] + rng.choice(tokens).group() + data[last:]
    # Truncate at a token boundary and duplicate the final delimiter.
    # This exercises incomplete statements and error recovery at EOF.
    if token.group() in {b";", b",", b"|", b"("}:
        return data[:last] + token.group() + b"\n"
    return data[:first] + b"\n"


def json_mutation(data, rng):
    try:
        value = json.loads(data)
    except (ValueError, UnicodeError, RecursionError):
        value = None
    options = [None, False, [], {}, "", 0, -1, 2**53, "é", "x" * rng.choice([31, 32, 255, 256])]
    boundary = rng.choice(options)
    if isinstance(value, list) and rng.randrange(2):
        if value and rng.randrange(2):
            value[rng.randrange(len(value))] = boundary
        else:
            value.append(boundary)
    elif isinstance(value, dict) and rng.randrange(2):
        key = rng.choice(list(value) or ["x"])
        value[key] = boundary
    else:
        value = rng.choice([boundary, [value, boundary], {"x": value, "edge": boundary}])
    return (json.dumps(value, ensure_ascii=True, separators=(",", ":")) + "\n").encode("ascii")


def cases(seeds, mode, strategy, rng):
    """Yield the seeds, then bounded mutations of them.

    Reject oversized seeds up front and cap the retries: a mutation that keeps
    exceeding MAX_INPUT must fail loudly instead of spinning forever.
    """
    seeds = tuple(seeds)
    if not seeds:
        raise ValueError("seed corpus is empty")
    largest = max(len(seed) for seed in seeds)
    if largest > MAX_INPUT:
        raise ValueError(f"seed is {largest} bytes, limit is {MAX_INPUT} bytes")
    mutator = {"jq-script": script_mutation, "json": json_mutation}.get(mode, byte_mutation)
    mutate = byte_mutation if strategy == "bytes" else mutator

    def generate():
        yield from seeds
        while True:
            for _ in range(MAX_MUTATION_ATTEMPTS):
                data = mutate(rng.choice(seeds), rng)
                if len(data) <= MAX_INPUT:
                    break
            else:
                raise ValueError(
                    f"no candidate within {MAX_INPUT} bytes after "
                    f"{MAX_MUTATION_ATTEMPTS} attempts")
            yield data

    return generate()
