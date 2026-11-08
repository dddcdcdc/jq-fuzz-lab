def clean: gsub("[ ]+"; " ") | sub("^ +"; "");
"  example   text" | #lean
