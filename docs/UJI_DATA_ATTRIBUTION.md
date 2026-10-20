# UJIIndoorLoc empirical data attribution and modification notice

**Original dataset:** Joaquín Torres-Sospedra, Raúl Montoliu, Adolfo Martínez-Usó, Tomás Arnau and Joan Avariento. *UJIIndoorLoc*, UCI Machine Learning Repository (2014). DOI: https://doi.org/10.24432/C5MS59.

**Source and license:** https://archive.ics.uci.edu/dataset/310/ujiindoorloc; **Creative Commons Attribution 4.0 International (CC BY 4.0)**, https://creativecommons.org/licenses/by/4.0/.

**This repository's changes:** Three building-level evaluation units (U01–U03) have been selected from the existing harmonized ESWA research workspace; each retains its study training and test partitions and observed RSS values. AP columns/identifiers were relabeled to the stable anonymous `AP1`, `AP2`, ... namespace, spatial coordinates were expressed in a local-relative metric frame, and rows were serialized as gzipped CSV with sparse `rss_json` dictionaries and source-independent scan keys. The submitted study uses unit-specific splits, **not** necessarily the official source train/validation split. The transformed versions are not endorsed by the original dataset authors.

Only the derived dataset files are licensed under the terms applicable to UJIIndoorLoc; they are not part of the software MIT license. Keep this notice when redistributing the data.
