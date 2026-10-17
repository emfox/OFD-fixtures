# OFD fixtures

Sample OFD documents used as test fixtures by [SteleOFD](https://github.com/emfox/SteleOFD).
They live in their own repository because of two problems:

1. **Provenance.** Upstream sample sets are served from moving references — a
   `master` branch, a file-sharing blob, an article attachment. Pinning any of
   those does not pin the bytes.
2. **Size.** The set is ~27 MB. A repository that commits it pays for that
   weight in every clone, forever, whether or not the samples are ever needed.

Here the bytes are the version. `manifest.json` records a SHA-256 for every
file, so a consumer that pins one commit of this repository and verifies the
hashes against that manifest knows exactly what it parsed.

## Layout

```
ofdrw/          22 files, 15 MB
gb-t-33190/
  Desktop.zip   11.6 MB   the publisher's archive, exactly as distributed
manifest.json
```

| Set | Upstream | Licence |
| --- | --- | --- |
| `ofdrw/` | [ofdrw/ofdrw](https://github.com/ofdrw/ofdrw) | Apache-2.0 |
| `gb-t-33190/` | [open-source-toolkit/886653](https://gitcode.com/open-source-toolkit/886653) | Conformance material published alongside GB/T 33190-2016 |

### ofdrw/

The reference Java implementation's own test resources, copied verbatim. The
`origin` field of each entry in `manifest.json` gives the path it came from
upstream, so a sample can always be traced back to the module that uses it.

### gb-t-33190/

The sample set distributed with the standard, stored as the one archive the
publisher ships and nothing else:

- `Desktop.zip` — byte-for-byte what the module publishes, 11,616,209 bytes,
  hash `dcbd0e24cab4fdb251d149a7aeca711faeda513ababaea1d72080d35bcd1eb67`.
  It arrives as an article attachment, so the attachment is the primary
  source; the module page it is attached to is
  [gitcode.com/open-source-toolkit/886653](https://gitcode.com/open-source-toolkit/886653),
  announced at
  [blog.csdn.net/gitblog_09791/article/details/143283031](https://blog.csdn.net/gitblog_09791/article/details/143283031).

Keeping only the published archive means every byte here can be checked
against the source: nothing is unpacked, renamed or reconstructed. The
consequence is that reading the samples takes two steps.

```
Desktop.zip
└── ofd标准测试文件.zip         (stored, not deflated)
    └── 6.1.001 Entry全部不压缩.ofd … 6.2.006 各级目录下有无用内容.ofd
```

Both layers are ZIPs and both store the Chinese names as GBK bytes with the
UTF-8 flag clear, so a naive reader sees mojibake. `scripts/fixtures.py` in
SteleOFD does the peeling and the `cp437` → `gbk` round-trip that recovers the
names.

`Desktop.zip` also carries one unrelated mind-map image (`你当像鸟飞往你的山.png`,
a reading note) that has nothing to do with OFD. It stays because it is part of
the original archive, not because anything uses it.

Filenames carry the clause they exercise — `6.2.001 正常文件结构.ofd` is the
well-formed baseline, `6.1.004 Entry不合理压缩.ofd` a badly compressed archive,
and so on.

## manifest.json

```json
{
  "version": 2,
  "sets": {
    "ofdrw": {
      "upstream": "https://github.com/ofdrw/ofdrw",
      "licence": "Apache-2.0",
      "note": "...",
      "files": {
        "1.ofd": {
          "origin": "ofdrw-converter/src/test/resources/1.ofd",
          "bytes": 16048,
          "sha256": "bf41627e..."
        }
      }
    },
    "gb-t-33190": {
      "upstream": "https://gitcode.com/open-source-toolkit/886653",
      "page": "https://blog.csdn.net/gitblog_09791/article/details/143283031",
      "licence": "Published with GB/T 33190-2016 as conformance material.",
      "note": "Desktop.zip exactly as published. ...",
      "files": {
        "Desktop.zip": {
          "origin": "Desktop.zip as published on gitcode.com/open-source-toolkit/886653",
          "bytes": 11616209,
          "sha256": "dcbd0e24..."
        }
      }
    }
  }
}
```

`origin` names where a file came from inside its upstream — a path for
`ofdrw/`, the archive it was peeled out of for `gb-t-33190/`. `bytes` and
`sha256` describe the file as stored here.

## Consuming this repository

Do not track a branch. Pin a commit and verify.

```bash
BASE=https://raw.githubusercontent.com/emfox/OFD-fixtures/<commit>/
curl -fsSL "${BASE}manifest.json"            # read the expected hashes
curl -fsSL "${BASE}ofdrw/1.ofd"              # then the file
sha256sum 1.ofd                              # compare against the manifest
```

Fetching file by file is slow enough over GitHub's raw path to be worth
avoiding for a whole set: 13 requests took minutes, where one
`https://codeload.github.com/emfox/OFD-fixtures/tar.gz/<commit>` took 16
seconds for all 25 MB. SteleOFD's `scripts/fixtures.py` does the latter and
holds every member it extracts to its hash before writing it.

Files are stored uncompressed and unmodified, so the hash of the downloaded
bytes is the hash in the manifest. Some samples are themselves ZIP archives
almost entirely occupied by already-compressed streams, so packing them again
would save little and would cost the property above.

## Rights

This repository redistributes third-party material. It grants no licence of its
own beyond what each upstream already grants; see [NOTICE](NOTICE). If you hold
rights to a file here and want it removed, open an issue.
