def trim: ltrimstr("prefix-");
["prefix-foo", "bar"] | map(trim | join(",")
