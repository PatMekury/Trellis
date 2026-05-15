"""Build a DHIS2-importable Nigeria org-unit hierarchy from the existing Trellis GeoPackage.

Output: nigeria_orgunits.json — POST this to /api/metadata?importMode=COMMIT&identifier=UID.
Hierarchy:
  level 1: Nigeria (root)
  level 2: Delta State
  level 3: 25 LGAs in Delta
  level 4: 267 wards in Delta

DHIS2 UIDs must be 11 chars, alphanumeric, start with a letter. We generate deterministic
UIDs from a SHA-1 of the org-unit canonical name, base62-encoded, padded.
"""
import json, hashlib, string
from pathlib import Path
import geopandas as gpd

# Project root, resolved relative to this file (was a sandbox-absolute path).
from pathlib import Path as _Path
ROOT_DIR = _Path(__file__).resolve().parent.parent.parent

DATA = (ROOT_DIR / "data")
OUT_DIR = (ROOT_DIR / "dhis2/local")
TMP_GPKG = "/tmp/trellis_delta_wards.gpkg"

ALPHABET = string.ascii_letters + string.digits  # 62 chars
def gen_uid(seed):
    """Deterministic 11-char UID, starts with a letter, alphanumeric."""
    h = hashlib.sha1(seed.encode()).digest()
    n = int.from_bytes(h, "big")
    # First char must be a letter
    chars = []
    chars.append(string.ascii_letters[n % 52])
    n //= 52
    for _ in range(10):
        chars.append(ALPHABET[n % 62])
        n //= 62
    return "".join(chars)

# Load
delta_wards = gpd.read_file(TMP_GPKG, layer="delta_wards")
delta_lgas = gpd.read_file(TMP_GPKG, layer="delta_lgas")
print(f"Loaded: {len(delta_wards)} wards, {len(delta_lgas)} LGAs")

org_units = []
uid_lookup = {}

# Nigeria root
ng_uid = gen_uid("Nigeria")
org_units.append({
    "id": ng_uid, "name": "Nigeria", "shortName": "Nigeria",
    "level": 1, "openingDate": "1900-01-01",
})
uid_lookup["Nigeria"] = ng_uid

# Delta State
delta_uid = gen_uid("Nigeria/Delta")
org_units.append({
    "id": delta_uid, "name": "Delta State", "shortName": "Delta",
    "level": 2, "parent": {"id": ng_uid},
    "openingDate": "1991-08-27",
})
uid_lookup["Delta State"] = delta_uid

# LGAs (level 3)
for _, r in delta_lgas.iterrows():
    lga_name = r["lganame"]
    uid = gen_uid(f"Nigeria/Delta/{lga_name}")
    org_units.append({
        "id": uid, "name": lga_name, "shortName": lga_name[:50],
        "level": 3, "parent": {"id": delta_uid},
        "openingDate": "1991-08-27",
    })
    uid_lookup[f"LGA|{lga_name}"] = uid

# Wards (level 4)
for _, r in delta_wards.iterrows():
    lga_name = r["lganame"]
    ward_name = r["wardname"]
    parent_uid = uid_lookup.get(f"LGA|{lga_name}")
    if not parent_uid:
        print(f"  WARN: no LGA UID for {lga_name}")
        continue
    uid = gen_uid(f"Nigeria/Delta/{lga_name}/{ward_name}")
    org_units.append({
        "id": uid, "name": ward_name, "shortName": ward_name[:50],
        "level": 4, "parent": {"id": parent_uid},
        "openingDate": "1991-08-27",
    })
    uid_lookup[f"Ward|{lga_name}|{ward_name}"] = uid

# UID uniqueness check
uids = [o["id"] for o in org_units]
if len(uids) != len(set(uids)):
    raise RuntimeError(f"UID collision: {len(uids)} ids, {len(set(uids))} unique")

# Sanity: all parents reference valid uids
all_uids = set(uids)
for o in org_units:
    if "parent" in o and o["parent"]["id"] not in all_uids:
        raise RuntimeError(f"Bad parent ref: {o['name']} -> {o['parent']['id']}")

print(f"Total org units: {len(org_units)}")
print(f"  level 1: 1, level 2: 1, level 3: {len(delta_lgas)}, level 4: {len(delta_wards)}")
print(f"All UIDs unique: {len(uids) == len(set(uids))}")
print(f"All parent refs valid: yes")

with open(OUT_DIR / "nigeria_orgunits.json", "w") as f:
    json.dump({"organisationUnits": org_units}, f, indent=2)
print(f"Wrote {OUT_DIR / 'nigeria_orgunits.json'}")

# Save the ward UID lookup for the push script
with open(OUT_DIR / "ward_uid_lookup.json", "w") as f:
    json.dump(uid_lookup, f, indent=2)
print(f"Wrote {OUT_DIR / 'ward_uid_lookup.json'}")