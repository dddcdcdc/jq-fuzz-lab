def clean: gsub("[ ]+"; " ") | sub("^ +"; "");
"  example   text" | clean
