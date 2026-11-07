#!/usr/bin/env bash
# Use a fresh, unpacked jq 1.8.0 release source tarball on Linux.
set -euo pipefail
here=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo=$(cd -- "$here/../.." && pwd)
source_dir=$(cd -- "${1:?pass the directory of the unpacked jq 1.8.0 source release}" && pwd)
cd -- "$source_dir"
clang -O2 -c "$here/trace.c" -o fuzz-trace.o
CC=clang CFLAGS="-O1 -g -fno-omit-frame-pointer -fsanitize=address -fsanitize-coverage=trace-pc-guard" \
  LDFLAGS="-fsanitize=address" LIBS="$source_dir/fuzz-trace.o" \
  ./configure --with-oniguruma=builtin --disable-shared --disable-docs
make -j2
install -m 755 jq "$repo/targets/jq-coverage/jq"
