"""Generate the deterministic jq case corpus at targets/jq-cases/cases.jsonl.

Each case fixes the argv, the standard input, and the expected result, so a run
can be reviewed case by case. Expectations come from the jq 1.8 manual and from
independent Python models of the specified behaviour; they are not copied from
the output of the binary under test.
"""
import base64
import json
from pathlib import Path
import random

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "targets" / "jq-cases" / "cases.jsonl"
CASES = []


def add(cid, argv, stdin="", exit_code=0, stdout=None, stderr=None,
        kind=None, category="", versions=None, files=None):
    expect = {"exit": exit_code}
    if stdout is not None:
        expect["stdout"] = stdout
    if stderr:
        expect["stderr_contains"] = stderr
    if kind:
        expect["kind"] = kind
    case = {"id": cid, "category": category, "argv": argv, "stdin": stdin, "expect": expect}
    if versions:
        case["versions"] = versions
    if files:
        case["files"] = files
    CASES.append(case)


def compact(cid, category, script, stdin, expected, argv=("-c",)):
    """One-liner for an exact-text case with compact JSON output."""
    add(cid, [*argv, script], stdin, stdout=expected + "\n", category=category)


def lines(values):
    return "".join(value + "\n" for value in values)


# ---------------------------------------------------------------- normal output
NORMAL = [
    ("field", ".name", '{"name":"Ada"}', '"Ada"'),
    ("nested", ".user.name", '{"user":{"name":"Bo"}}', '"Bo"'),
    ("missing", ".missing", '{"a":1}', "null"),
    ("index", ".items[1]", '{"items":[10,20,30]}', "20"),
    ("index.negative", ".items[-1]", '{"items":[10,20,30]}', "30"),
    ("index.out-of-range", ".items[5]", '{"items":[10,20]}', "null"),
    ("slice", ".items[1:3]", '{"items":[10,20,30,40]}', "[20,30]"),
    ("slice.open-left", ".items[1:]", '{"items":[10,20,30]}', "[20,30]"),
    ("slice.open-right", ".items[:2]", '{"items":[10,20,30]}', "[10,20]"),
    ("bracket-key", '.["a-b"]', '{"a-b":1}', "1"),
    ("unicode-key", '.["\u540d\u5b57"]', '{"\u540d\u5b57":"\u5f20\u4e09"}', '"\u5f20\u4e09"'),
    ("nested-index", ".a[0].b", '{"a":[{"b":7}]}', "7"),
    ("iterate.array", ".[]", "[1,2]", "1\n2"),
    ("iterate.object", ".[]", '{"a":1,"b":2}', "1\n2"),
    ("iterate.field", ".[]|.a", '[{"a":1},{"a":2}]', "1\n2"),
    ("map.field", "map(.x)", '[{"x":1},{"x":2}]', "[1,2]"),
    ("map.increment", "map(.+1)", "[1,2,3]", "[2,3,4]"),
    ("map.select", "map(select(.>1))", "[1,2,3]", "[2,3]"),
    ("filter.even", "[.[]|select(.%2==0)]", "[1,2,3,4]", "[2,4]"),
    ("map.type", "map(type)", '[1,"a",null,true,[],{}]',
     '["number","string","null","boolean","array","object"]'),
    ("shorthand-object", "{name, age}", '{"name":"Ada","age":30,"x":1}',
     '{"name":"Ada","age":30}'),
    ("rename-field", "{n: .name}", '{"name":"Ada"}', '{"n":"Ada"}'),
    ("merge-object", "{a:1} + {b:2}", "null", '{"a":1,"b":2}'),
    ("deep-merge", ". * {a: 9}", '{"a":1,"b":2}', '{"a":9,"b":2}'),
    ("delete-field", "del(.a)", '{"a":1,"b":2}', '{"b":2}'),
    ("to-entries", "to_entries", '{"a":1}', '[{"key":"a","value":1}]'),
    ("entries-roundtrip", "to_entries|from_entries", '{"a":1,"b":2}', '{"a":1,"b":2}'),
    ("with-entries", "with_entries(.value += 1)", '{"a":1}', '{"a":2}'),
    ("keys", "keys", '{"b":1,"a":2}', '["a","b"]'),
    ("keys-unsorted", "keys_unsorted", '{"b":1,"a":2}', '["b","a"]'),
    ("has.true", 'has("a")', '{"a":1}', "true"),
    ("has.false", 'has("z")', '{"a":1}', "false"),
    ("update-each", ".[] |= .+1", '{"a":1,"b":2}', '{"a":2,"b":3}'),
    ("map-values", "map_values(.+1)", '{"a":1}', '{"a":2}'),
    ("sort.numbers", "sort", "[3,1,2]", "[1,2,3]"),
    ("sort.strings", "sort", '["b","a"]', '["a","b"]'),
    ("sort-by", "sort_by(.k)", '[{"k":2},{"k":1}]', '[{"k":1},{"k":2}]'),
    ("unique", "unique", "[3,1,3]", "[1,3]"),
    ("group-by", "group_by(.k)|map(length)", '[{"k":1},{"k":1},{"k":2}]', "[2,1]"),
    ("add.numbers", "add", "[1,2,3]", "6"),
    ("add.strings", "add", '["a","b"]', '"ab"'),
    ("min", "min", "[3,1,2]", "1"),
    ("max", "max", "[3,1,2]", "3"),
    ("length.array", "length", "[1,2,3]", "3"),
    ("length.string", "length", '"h\u00e9llo"', "5"),
    ("length.object", "length", '{"a":1}', "1"),
    ("length.null", "length", "null", "0"),
    ("flatten", "flatten", "[[1,[2]],[3]]", "[1,2,3]"),
    ("any", "any", "[false,true]", "true"),
    ("all", "all", "[true,true]", "true"),
    ("reverse", "reverse", "[1,2,3]", "[3,2,1]"),
    ("lowercase", "ascii_downcase", '"ABC"', '"abc"'),
    ("uppercase", "ascii_upcase", '"abc"', '"ABC"'),
    ("ltrimstr", 'ltrimstr("ab")', '"abc"', '"c"'),
    ("rtrimstr", 'rtrimstr("bc")', '"abc"', '"a"'),
    ("startswith", 'startswith("ab")', '"abc"', "true"),
    ("split", 'split(",")', '"a,b,c"', '["a","b","c"]'),
    ("join", 'join("-")', '["a","b"]', '"a-b"'),
    ("gsub", 'gsub("a";"b")', '"aaa"', '"bbb"'),
    ("sub", 'sub("a";"b")', '"aaa"', '"baa"'),
    ("test", 'test("^a+$")', '"aaa"', "true"),
    ("capture", 'capture("(?<x>a+)")', '"aaa"', '{"x":"aaa"}'),
    ("tostring", "tostring", "1", '"1"'),
    ("tonumber", "tonumber", '"42"', "42"),
    ("explode-implode", "explode|implode", '"AB"', '"AB"'),
    ("base64-encode", "@base64", '"hi"', '"aGk="'),
    ("base64-decode", "@base64d", '"aGk="', '"hi"'),
    ("uri-encode", "@uri", '"a b"', '"a%20b"'),
    ("json-encode", "@json", '{"a":1}', '"{\\"a\\":1}"'),
    ("csv-encode", "@csv", '[1,"a"]', '"1,\\"a\\""'),
    ("indices", 'indices("a")', '"banana"', "[1,3,5]"),
    ("if-then", 'if .a > 1 then "big" else "small" end', '{"a":2}', '"big"'),
    ("try-catch", 'try (.a.b) catch "err"', '{"a":1}', '"err"'),
    ("alternative", '.a // "default"', "{}", '"default"'),
    ("alternative.default", '(.a // 0) + 1', "{}", "1"),
    ("range", "[range(3)]", "null", "[0,1,2]"),
    ("limit", "limit(2; .[])", "[1,2,3]", "1\n2"),
    ("first", "first(.[])", "[1,2]", "1"),
    ("last", "last(.[])", "[1,2]", "2"),
    ("reduce", "reduce .[] as $x (0; .+$x)", "[1,2,3]", "6"),
    ("foreach", "foreach .[] as $x (0; .+$x)", "[1,2,3]", "1\n3\n6"),
    ("getpath", 'getpath(["a","b"])', '{"a":{"b":5}}', "5"),
    ("setpath", 'setpath(["a"];9)', '{"a":1}', '{"a":9}'),
    ("walk", 'walk(if type=="number" then .+1 else . end)', '{"a":[1,2]}', '{"a":[2,3]}'),
    ("json-roundtrip", "tojson|fromjson", '{"a":[1,2]}', '{"a":[1,2]}'),
]
for name, script, stdin, expected in NORMAL:
    compact(f"normal.{name}", "normal", script, stdin, expected)

# ------------------------------------------------------------------- boundaries
compact("boundary.empty-object.keys", "boundary", "keys", "{}", "[]")
compact("boundary.empty-array.length", "boundary", "length", "[]", "0")
compact("boundary.empty-array.add", "boundary", "add", "[]", "null")
compact("boundary.empty-array.min", "boundary", "min", "[]", "null")
compact("boundary.empty-string.length", "boundary", "length", '""', "0")
compact("boundary.empty-string.split", "boundary", 'split(",")', '""', '[]')
compact("boundary.duplicates", "boundary", "unique", "[1,1,1]", "[1]")
compact("boundary.duplicates.length", "boundary", "length", "[7,7,7]", "3")
compact("boundary.cjk.length", "boundary", "length", '"\u5f20\u4e09"', "2")
compact("boundary.cjk.split", "boundary", 'split("\uff0c")', '"\u7532\uff0c\u4e59"',
        '["\u7532","\u4e59"]')
compact("boundary.escaped-tab", "boundary", ".", '"a\\tb"', '"a\\tb"')
compact("boundary.escaped-quote", "boundary", ".", '"a\\"b"', '"a\\"b"')
compact("boundary.escaped-backslash", "boundary", ".", '"a\\\\b"', '"a\\\\b"')
compact("boundary.empty-key", "boundary", '.[""]', '{"":1}', "1")
compact("boundary.whitespace", "boundary", ".", '  {"a":1}  ', '{"a":1}')
compact("boundary.several-values", "boundary", ".", "1 2 3", "1\n2\n3")
compact("boundary.null.tostring", "boundary", "tostring", "null", '"null"')
compact("boundary.null.index", "boundary", ".a.b", "null", "null")
compact("boundary.nested-empty", "boundary", "flatten", "[[],[[]]]", "[]")
compact("boundary.flatten-depth", "boundary", "flatten(1)", "[1,[2,[3]]]", "[1,2,[3]]")
compact("boundary.string-slice", "boundary", ".[1:2]", '"abc"', '"b"')
compact("boundary.int-max-safe", "boundary", ".", "9007199254740991", "9007199254740991")
compact("boundary.int-min-safe", "boundary", ".", "-9007199254740991", "-9007199254740991")
compact("boundary.zero", "boundary", ".", "-0", "-0")
compact("boundary.long-string", "boundary", "length", '"%s"' % ("x" * 256), "256")
compact("boundary.long-array", "boundary", "length", json.dumps(list(range(100))), "100")
compact("boundary.sorted-array", "boundary", "sort", json.dumps(list(range(100))),
        json.dumps(list(range(100)), separators=(",", ":")))
compact("boundary.deep-array", "boundary", ".", json.dumps([[[[[1]]]]]), "[[[[[1]]]]]")
compact("boundary.deep-slice", "boundary", ".[0][0][0]", json.dumps([[[7]]]), "7")
compact("boundary.multi-json-slurp", "boundary", "length", '[1]\n[2]\n[3]', "3", argv=("-c", "-s"))
add("boundary.empty-input", ["-c", "."], "", stdout="", category="boundary")
add("boundary.empty-object.iterate", ["-c", ".[]"], "{}", stdout="", category="boundary")
add("boundary.input-with-newline", ["-c", "length"], "{\n\"a\": 1\n}\n", stdout="1\n",
    category="boundary")
add("boundary.long-string-roundtrip", ["-c", "length"], '"%s"' % ("ab" * 64), stdout="128\n",
    category="boundary")

# ---------------------------------------------------------------------- errors
add("error.invalid-json.brace", ["-c", "."], "{", exit_code=5, category="error",
    stderr=["parse error"])
add("error.invalid-json.value", ["-c", "."], '{"a":}', exit_code=5, category="error",
    stderr=["parse error"])
add("error.invalid-json.truncated", ["-c", "."], "[1,2", exit_code=5, category="error",
    stderr=["parse error"])
add("error.script.eof", ["-c", ".a+"], '{"a":1}', exit_code=3, category="error",
    stderr=["syntax error"])
add("error.script.bracket", ["-c", ".["], "{}", exit_code=3, category="error",
    stderr=["syntax error"])
add("error.script.unknown-function", ["-c", "nosuchfn"], "null", exit_code=3, category="error",
    stderr=["is not defined"])
add("error.iterate-number", ["-c", ".[]"], "5", exit_code=5, category="error",
    stderr=["Cannot iterate over number"])
add("error.iterate-null", ["-c", ".[]"], "null", exit_code=5, category="error",
    stderr=["Cannot iterate over null"])
add("error.index.number", ["-c", ".a.b"], '{"a":1}', exit_code=5, category="error",
    stderr=['Cannot index number with string "b"'])
add("error.index-object-number", ["-c", ".[0]"], "{}", exit_code=5, category="error",
    stderr=["Cannot index object with number"])
add("error.index-array-string", ["-c", '.["a"]'], "[1]", exit_code=5, category="error",
    stderr=["Cannot index array with string"])
add("error.divide-by-zero", ["-c", "1/0"], "null", exit_code=5, category="error",
    stderr=["divisor is zero"])
add("error.raise", ["-c", 'error("boom")'], "null", exit_code=5, category="error",
    stderr=["boom"])
add("error.tonumber", ["-c", "tonumber"], '"abc"', exit_code=5, category="error",
    stderr=["cannot be parsed as a number"])
add("error.fromjson", ["-c", "fromjson"], '"nope"', exit_code=5, category="error",
    stderr=["Invalid numeric literal"])
add("error.has-on-array", ["-c", 'has("a")'], "[1]", exit_code=5, category="error",
    stderr=["Cannot check whether array has a string key"])
add("error.length-boolean", ["-c", "length"], "true", exit_code=5, category="error",
    stderr=["has no length"])
add("error.base64-decode", ["-c", "@base64d"], '"@@@"', exit_code=5, category="error",
    stderr=["not valid base64"])
add("error.split-number", ["-c", 'split(",")'], "1", exit_code=5, category="error",
    stderr=["must be strings"])
add("error.join-object", ["-c", 'join("-")'], '[{"a":1}]', exit_code=5, category="error",
    stderr=["cannot be added"])
add("error.unknown-option", ["--bogus", "-n", "."], "", exit_code=2, category="error",
    stderr=["Unknown option --bogus"])
add("error.missing-file", ["-c", ".", "no-such-input.json"], "", exit_code=2, category="error",
    stderr=["Could not open file", "No such file"])
add("error.undefined-variable", ["-c", "$y"], "null", exit_code=3, category="error",
    stderr=["is not defined"])
add("error.invalid-escape", ["-c", "."], '"\\q"', exit_code=5, category="error",
    stderr=["Invalid escape"])
add("error.assertion-text-is-rejected", ["-c", 'error("Assertion failed: application message")'],
    "null", exit_code=5, kind="rejected", category="error", stderr=["Assertion failed"])
add("error.sanitizer-text-is-rejected", ["-c", 'error("ERROR: AddressSanitizer: fake report")'],
    "null", exit_code=5, kind="rejected", category="error", stderr=["AddressSanitizer"])

# ------------------------------------------------------------------ properties
rng = random.Random(20261108)
values, arrays, objects = [], [], []
for _ in range(8):
    arrays.append([rng.randrange(-50, 51) for _ in range(rng.randrange(0, 9))])
    objects.append({"x": rng.randrange(-20, 21), "tag": rng.choice(["a", "b", "c"])})
for _ in range(6):
    values.append(rng.choice([
        {"a": rng.randrange(0, 100), "b": [rng.choice([True, False, None]), "s"]},
        [rng.randrange(0, 9), [rng.randrange(0, 9)], {"k": "v"}],
        rng.choice(["", "abc", "\u4e2d\u6587", "line\nbreak"]),
    ]))


def canon(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


for index, value in enumerate(values, 1):
    compact(f"property.json-roundtrip.{index:02}", "property", "tojson|fromjson",
            canon(value), canon(value))
for index, array in enumerate(arrays, 1):
    compact(f"property.sort.order.{index}", "property", "sort", canon(array), canon(sorted(array)))
    compact(f"property.sort.idempotent.{index}", "property", "sort|sort", canon(array),
            canon(sorted(array)))
    compact(f"property.unique.size.{index}", "property", "unique|length", canon(array),
            str(len(set(array))))
    compact(f"property.length.{index}", "property", "length", canon(array), str(len(array)))
for index, item in enumerate(objects, 1):
    compact(f"property.map-field.{index}", "property", "map(.x)",
            canon([{"x": item["x"]}, {"x": item["x"] + 1}]), canon([item["x"], item["x"] + 1]))
    compact(f"property.entries.{index}", "property", "to_entries|from_entries", canon(item),
            canon(item))
    compact(f"property.keys.{index}", "property", "keys", canon(item), canon(sorted(item)))
    compact(f"property.group-count.{index}", "property", "group_by(.k)|map(length)",
            canon([{"k": 1}, {"k": 1}, {"k": 2}]), "[2,1]")

sums = [sum(array) for array in arrays]
for index, (array, total) in enumerate(zip(arrays, sums), 1):
    compact(f"property.add.{index}", "property", "add", canon(array), canon(total))

for index, text in enumerate(["", "a", "abc", "\u4e2d\u6587", "x" * 32], 1):
    encoded = base64.b64encode(text.encode()).decode()
    compact(f"property.base64-roundtrip.{index}", "property", "@base64|@base64d", canon(text),
            canon(text))
    compact(f"property.base64-value.{index}", "property", "@base64", canon(text), canon(encoded))

# --------------------------------------------------------- parameter variation
pretty = '{\n  "a": 1,\n  "b": [\n    2\n  ]\n}\n'
add("params.pretty", [".", ], '{"a":1,"b":[2]}', stdout=pretty, category="params")
add("params.compact", ["-c", "."], '{"a":1,"b":[2]}', stdout='{"a":1,"b":[2]}\n',
    category="params")
add("params.tab", ["--tab", "."], '{"a":1}', stdout='{\n\t"a": 1\n}\n', category="params")
add("params.indent-4", ["--indent", "4", "."], '{"a":1}', stdout='{\n    "a": 1\n}\n',
    category="params")
add("params.raw-output", ["-r", ".a"], '{"a":"x"}', stdout="x\n", category="params")
add("params.join-output", ["-j", ".a"], '{"a":"x"}', stdout="x", category="params")
add("params.raw-join", ["-r", "-j", ".a"], '{"a":"x"}', stdout="x", category="params")
add("params.slurp", ["-s", "-c", "length"], '{"a":1}{"a":2}', stdout="2\n", category="params")
add("params.slurp-compact", ["-s", "-c", ".[0].a"], '{"a":1}{"a":2}', stdout="1\n",
    category="params")
add("params.null-input", ["-n", "-c", "1+1"], "", stdout="2\n", category="params")
add("params.arg", ["-n", "-c", "--arg", "n", "Ada", "$n"], "", stdout='"Ada"\n',
    category="params")
add("params.argjson", ["-n", "-c", "--argjson", "n", '{"k":1}', "$n.k"], "", stdout="1\n",
    category="params")
add("params.arg-with-slurp", ["-s", "-c", "--arg", "n", "Ada", "[$n, length]"], '{"a":1}',
    stdout='["Ada",1]\n', category="params")
add("params.exit-status.true", ["-e", ".a"], '{"a":1}', stdout="1\n", exit_code=0,
    category="params")
add("params.exit-status.empty", ["-e", "empty"], '{"a":1}', stdout="", exit_code=4,
    category="params")
add("params.sort-keys", ["-S", "-c", "."], '{"b":1,"a":2}', stdout='{"a":2,"b":1}\n',
    category="params")
add("params.ascii-output", ["-a", "-c", "."], '{"n":"\u5f20\u4e09"}',
    stdout='{"n":"\\u5f20\\u4e09"}\n', category="params")
add("params.ascii-compact-sort", ["-a", "-c", "-S", "."], '{"b":"\u4e2d","a":1}',
    stdout='{"a":1,"b":"\\u4e2d"}\n', category="params")
add("params.raw-input", ["--raw-input", "-c", "."], "a\nb\n", stdout='"a"\n"b"\n',
    category="params")
add("params.raw-input-slurp", ["--raw-input", "-s", "-c", "."], "a\nb\n",
    stdout='"a\\nb\\n"\n', category="params")
add("params.two-files", ["-c", ".v", "a.json", "b.json"], "",
    stdout="1\n2\n", category="params",
    files={"a.json": '{"v":1}', "b.json": '{"v":2}'})
add("params.input-filename", ["-c", "input_filename", "a.json"], "", stdout='"a.json"\n',
    category="params", files={"a.json": '{"v":1}'})
add("params.from-file", ["-n", "--from-file", "prog.jq"], "", stdout="3\n",
    category="params", files={"prog.jq": "1 + 2\n"})
add("params.compact-from-file", ["-c", "--from-file", "prog.jq"], '{"a":1}', stdout="[1]\n",
    category="params", files={"prog.jq": "[.a]\n"})

# ------------------------------------------------------- version-specific cases
TRUNCATED = [("(", "("), ("bracket", "["), ("object", "{"), ("if", "if"),
             ("access", ".["), ("binding", "1 as")]
for name, script in TRUNCATED:
    add(f"regression.truncated-{name}.1.8.0", ["-n", "--from-file", "case.jq"], "",
        exit_code=3221226505, kind="crash", category="regression",
        stderr=["Assertion failed: end > loc.start"], versions=["jq 1.8.0"],
        files={"case.jq": script + "\n"})
    add(f"regression.truncated-{name}.1.8.1", ["-n", "--from-file", "case.jq"], "",
        exit_code=3, kind="rejected", category="regression", stderr=["syntax error"],
        versions=["jq 1.8.1"], files={"case.jq": script + "\n"})

# ------------------------------------------------------------------- emit file
OUTPUT.parent.mkdir(parents=True, exist_ok=True)
with OUTPUT.open("w", encoding="utf-8", newline="\n") as handle:
    for case in CASES:
        handle.write(json.dumps(case, ensure_ascii=False, separators=(",", ":")) + "\n")
counts = {}
for case in CASES:
    counts[case["category"]] = counts.get(case["category"], 0) + 1
print(f"wrote {len(CASES)} cases to {OUTPUT}")
print(", ".join(f"{name}={count}" for name, count in sorted(counts.items())))
