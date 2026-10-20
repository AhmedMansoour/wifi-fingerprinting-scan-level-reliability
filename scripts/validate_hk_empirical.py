"""Validate the relabeled HK U09 empirical fingerprint table."""
import csv, gzip, hashlib, json, math, re
from pathlib import Path
P = Path(__file__).resolve().parents[1] / "data/empirical/hk_u09_ap_relative.csv.gz"
SHA = "b99bac3454e8f0f306c7fb8c012a7def5e277251c8013304e50e02ae51717078"
FIELDS = ["dataset","group","split","row_id","floor","x","y","rss_json"]
MAC = re.compile(r"(?<![a-fA-F0-9])(?:[a-fA-F0-9]{2}[:-]){5}[a-fA-F0-9]{2}(?![a-fA-F0-9])")
def validate(path=P):
    path=Path(path)
    raw=path.read_bytes()
    assert hashlib.sha256(raw).hexdigest()==SHA, "Dataset checksum differs"
    assert raw[:2]==b"\x1f\x8b"
    n={"train":0,"test":0}; ids=set(); levels=set(); aps=set()
    with gzip.open(path,"rt",encoding="utf-8",newline="") as f:
        reader=csv.DictReader(f)
        assert reader.fieldnames==FIELDS
        for row in reader:
            assert row["dataset"]=="HK_U09" and row["group"]=="HK_LOCAL"
            assert row["split"] in n
            n[row["split"]]+=1
            assert re.fullmatch(r"HK_SCAN_\d{5}",row["row_id"])
            ids.add(row["row_id"]); levels.add(int(row["floor"]))
            assert math.isfinite(float(row["x"])) and math.isfinite(float(row["y"]))
            rss=json.loads(row["rss_json"])
            assert isinstance(rss,dict)
            for ap,value in rss.items():
                assert re.fullmatch(r"AP[1-9][0-9]*",ap)
                assert math.isfinite(float(value))
                aps.add(ap)
            assert MAC.search(json.dumps(row)) is None, "MAC style string detected"
    assert n=={"train":3319,"test":831} and len(ids)==4150
    assert levels==set(range(11)) and aps=={f"AP{i}" for i in range(1,526)}
    return {"status":"passed","rows":len(ids),"splits":n,"floors":len(levels),"aps":len(aps)}
if __name__=="__main__":
    print(json.dumps(validate(),indent=2))
