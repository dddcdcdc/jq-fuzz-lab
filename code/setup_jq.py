"""Install the verified upstream jq binaries in the example target directories."""
import argparse
import hashlib
from pathlib import Path
import platform
import shutil
import tempfile
from urllib.request import urlopen

ASSETS = {
    "jq-windows-amd64.exe": (
        "b45fcbb27dcb9e9848ac39889a8bf86457b8d9d31e7c56387c6eab80008fd1f4",
        "23cb60a1354eed6bcc8d9b9735e8c7b388cd1fdcb75726b93bc299ef22dd9334",
    ),
    "jq-linux-amd64": (
        "8926c33326111bcd67a47a970b5a5db933ef9194ad925994934c639c76a0605c",
        "020468de7539ce70ef1bceaf7cde2e8c4f2ca6c3afb84642aabc5c97d9fc2a0d",
    ),
    "jq-macos-amd64": (
        "a594f3740bf570f0dbc43ff102a9034c17719d1bb5b40f0192751234d67f172a",
        "e80dbe0d2a2597e3c11c404f03337b981d74b4a8504b70586c354b7697a7c27f",
    ),
    "jq-macos-arm64": (
        "aaf1efbb376d6e3eaf61f63807c32c1df519f5857dfc4f581826fa2df4b715ae",
        "a9fe3ea2f86dfc72f6728417521ec9067b343277152b114f4e98d8cb0e263603",
    ),
}

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--old-file", type=Path, help="path to an already downloaded jq 1.8.0 binary")
parser.add_argument("--fixed-file", type=Path, help="path to an already downloaded jq 1.8.1 binary")
args = parser.parse_args()
system = {"Windows": "windows", "Linux": "linux", "Darwin": "macos"}.get(platform.system())
arch = {"x86_64": "amd64", "amd64": "amd64", "arm64": "arm64"}.get(platform.machine().lower())
suffix = ".exe" if system == "windows" else ""
asset = f"jq-{system}-{arch}{suffix}"
if asset not in ASSETS:
    parser.exit(2, f"Unsupported platform: {system}/{arch}\n")
root = Path(__file__).resolve().parents[1]
for tag, hash_value, local in zip(("1.8.0", "1.8.1"), ASSETS[asset], (args.old_file, args.fixed_file)):
    destination = root / "targets" / f"jq-{tag}" / f"jq{suffix}"
    if local is None and destination.is_file() and hashlib.sha256(destination.read_bytes()).hexdigest() == hash_value:
        print(f"jq {tag}: SHA-256 verified (already installed)")
        continue
    with tempfile.NamedTemporaryFile(dir=destination.parent, delete=False) as file:
        temp = Path(file.name)
        try:
            if local is None:
                with urlopen(f"https://github.com/jqlang/jq/releases/download/jq-{tag}/{asset}",
                             timeout=45) as response:
                    shutil.copyfileobj(response, file)
            else:
                with local.open("rb") as source:
                    shutil.copyfileobj(source, file)
        except BaseException:
            file.close()
            temp.unlink(missing_ok=True)
            raise
    try:
        if hashlib.sha256(temp.read_bytes()).hexdigest() != hash_value:
            parser.exit(2, f"jq {tag}: SHA-256 mismatch for {asset}\n")
        temp.chmod(0o755)
        temp.replace(destination)
    finally:
        temp.unlink(missing_ok=True)
    print(f"jq {tag}: SHA-256 verified")
