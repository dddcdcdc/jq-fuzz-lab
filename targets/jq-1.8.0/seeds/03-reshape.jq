def row($id; $name): {id: $id, name: $name};
[row(1; "ana"), row(2; "bo")] | map(.name)
