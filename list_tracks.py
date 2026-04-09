from db import open_database
import sys

db = open_database()

search = sys.argv[1].lower() if len(sys.argv) > 1 else ""

tracks = db.get_content()

results = []
for t in tracks:
    bpm = (t.BPM or 0) / 100
    if bpm < 155 or bpm > 185:
        continue
    title = t.Title or ""
    artist = getattr(t, "SrcArtistName", "") or ""
    if search and search not in title.lower() and search not in artist.lower():
        continue
    results.append((t.ID, bpm, artist, title))

results.sort(key=lambda x: (x[2], x[3]))

print(f"{'ID':<8} {'BPM':<6} {'Artist':<25} {'Title'}")
print("-" * 80)
for track_id, bpm, artist, title in results[:50]:
    print(f"{track_id:<8} {bpm:<6.1f} {artist[:24]:<25} {title[:40]}")

db.close()
