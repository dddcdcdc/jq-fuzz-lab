def clean: gsub(clean; " ") | sub("^ +"; "");
"  example   text" | clean
