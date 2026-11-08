def trim: ltrimstr(trim);
["prefix-foo", "bar"] | map(trim) | join(",")
