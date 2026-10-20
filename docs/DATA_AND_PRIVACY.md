# Data provenance

`examples/synthetic_combined/` remains the fully synthetic ten-unit software-test dataset.

`data/empirical/hk_u09_ap_relative.csv.gz` contains **real** HK RSS fingerprints: 4,150 scans (3,319 training; 831 test), 11 floor categories and 525 APs renamed AP1 through AP525. It uses relative metre coordinates and retains measured RSS and split memberships, while source BSSIDs, MAC addresses, SSIDs, router names, original scan IDs, coordinate origin and real map image/vector assets are absent. These are not synthetic observations, and the relative point arrangement has not been removed.

Its CSV schema is `dataset,group,split,row_id,floor,x,y,rss_json` with local dataset label `HK_U09`. Validate via `python scripts/validate_hk_empirical.py`. Only HK U09 is supplied among the ten real study units; the other nine and source hardware lookup tables remain unpublished. MIT is a software/synthetic license and does not automatically establish reuse rights in third-party empirical measurements.
