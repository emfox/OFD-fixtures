# OFD fixtures

Sample OFD documents used as test fixtures by [SteleOFD](https://github.com/emfox/SteleOFD).
They live in their own repository because of two problems:

1. **Provenance.** Upstream sample sets are served from moving references — a
   `master` branch, a file-sharing blob, an article attachment. Pinning any of
   those does not pin the bytes.
2. **Size.** The set is ~47 MB. A repository that commits it pays for that
   weight in every clone, forever, whether or not the samples are ever needed.

Here the bytes are the version. `manifest.json` records a SHA-256 for every
file, so a consumer that pins one commit of this repository and verifies the
hashes against that manifest knows exactly what it parsed.

## Layout

```
ofdrw/                    22 files, 15 MB
gb-t-33190/
  Desktop.zip             11.6 MB   the publisher's archive, unopened
  ofd标准测试文件.zip        10.2 MB   the inner archive, as shipped
  6.1.001 … .ofd          13 files, 10 MB   the inner archive, unpacked
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

The sample set distributed with the standard, kept in the three layers the
publisher shipped it in:

- `Desktop.zip` — byte-for-byte what the module publishes, hash
  `dcbd0e24cab4fdb251d149a7aeca711faeda513ababaea1d72080d35bcd1eb67`.
  It arrives as an article attachment, so the attachment is the primary
  source; the module page it is attached to is
  [gitcode.com/open-source-toolkit/886653](https://gitcode.com/open-source-toolkit/886653),
  announced at
  [blog.csdn.net/gitblog_09791/article/details/143283031](https://blog.csdn.net/gitblog_09791/article/details/143283031).
- `ofd标准测试文件.zip` — the archive inside it, also kept, because it is the
  layer that holds the filenames as the producer wrote them.
- the thirteen `.ofd` files beside it — that archive unpacked, with the GBK
  filenames restored to UTF-8. This is the layer consumers read.

The archive also carries an unrelated mind-map image (`你当像鸟飞往你的山.png`,
a reading note) that has nothing to do with OFD. It is **not** copied here: a
fixtures repository that starts accumulating whatever else happened to be in a
ZIP stops being a description of anything.

Filenames carry the clause they exercise — `6.2.001 正常文件结构.ofd` is the
well-formed baseline, `6.1.004 Entry不合理压缩.ofd` a badly compressed archive,
and so on. The distributor stores them as GBK bytes with the UTF-8 flag clear,
so a naive reader sees mojibake; the unpacked copies here are the names as
intended.

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
      "licence": "...",
      "note": "...",
      "files": { "Desktop.zip": { "...": "..." } }
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
avoiding for the whole set: 13 requests took minutes, where one
`https://codeload.github.com/emfox/OFD-fixtures/tar.gz/<commit>` took 16
seconds for all 25 MB. SteleOFD's `scripts/fixtures.py` does the latter and
holds every member to its hash before writing it.

Files are stored uncompressed and unmodified, so the hash of the downloaded
bytes is the hash in the manifest. Some samples are themselves ZIP archives
almost entirely occupied by already-compressed streams, so packing them again
would save little and would cost the property above.

## Rights

This repository redistributes third-party material. It grants no licence of its
own beyond what each upstream already grants; see [NOTICE](NOTICE). If you hold
rights to a file here and want it removed, open an issue.
