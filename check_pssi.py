from db import open_database, get_track
from pyrekordbox import AnlzFile
from pathlib import Path
import sys

track_id = sys.argv[1] if len(sys.argv) > 1 else input("Track ID: ")

db = open_database()
content = get_track(db, track_id)

ext_path = db.get_anlz_path(content, "EXT")
anlz = AnlzFile.parse_file(ext_path)
pssi = anlz.get_tag("PSSI")

print("PSSI type:", type(pssi))
print("PSSI attrs:", [a for a in dir(pssi) if not a.startswith("_")])
print()

# Try to get the raw data
try:
    data = pssi.get()
    print("pssi.get() type:", type(data))
    print("pssi.get():", data)
except Exception as e:
    print("pssi.get() failed:", e)

# Print all non-method attributes
for attr in dir(pssi):
    if attr.startswith("_"):
        continue
    try:
        val = getattr(pssi, attr)
        if not callable(val):
            print("  %s = %s" % (attr, repr(val)[:120]))
    except Exception as e:
        print("  %s => error: %s" % (attr, e))

db.close()
