# OFD fixtures

Sample OFD documents used as test fixtures by [SteleOFD](https://github.com/emfox/SteleOFD).
They live in their own repository because of two problems:

1. **Provenance.** Upstream sample sets are served from moving references — a
   `master` branch, or a file-sharing blob whose id the owner may rewrite.
   Pinning either of those does not pin the bytes.
2. **Size.** The set is ~25 MB across 35 files. A repository that commits them
   pays for that weight in every clone, forever, whether or not the samples are
   ever needed.

Here the bytes are the version. `manifest.json` records a SHA-256 for every
file, so a consumer that pins one commit of this repository and verifies the
hashes against that manifest knows exactly what it parsed.

## Layout

```
ofdrw/          22 files, 15 MB
gb-t-33190/     13 files, 11 MB
manifest.json
```

| Set | Upstream | Licence |
| --- | --- | --- |
| `ofdrw/` | [ofdrw/ofdrw](https://github.com/ofdrw/ofdrw) | Apache-2.0 |
| `gb-t-33190/` | [open-source-toolkit/886653](https://raw.atomgit.com/open-source-toolkit/886653) | Conformance material published alongside GB/T 33190-2016 |

`ofdrw/` is the reference Java implementation's own test resources, copied
verbatim; the `origin` field of each entry in `manifest.json` gives the path it
was taken from upstream.

`gb-t-33190/` is the sample set distributed with the standard: unpacked from
`ofd标准测试文件.zip` inside `Desktop.zip`. Filenames carry the clause they
exercise — `6.2.001 正常文件结构.ofd` is the well-formed baseline, `6.1.004
Entry不合理压缩.ofd` a badly compressed archive, and so on. The archive stores
the names in GBK; they are restored to UTF-8 here.

## manifest.json

```json
{
  "version": 1,
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
    }
  }
}
```

## Consuming this repository

Do not track a branch. Pin a commit and verify.

```bash
BASE=https://raw.githubusercontent.com/emfox/OFD-fixtures/<commit>/
curl -fsSL "${BASE}manifest.json"            # read the expected hashes
curl -fsSL "${BASE}ofdrw/1.ofd"              # then the file
sha256sum 1.ofd                              # compare against the manifest
```

Files are stored uncompressed and unmodified, so the hash of the downloaded
bytes is the hash in the manifest. Some samples are themselves ZIP archives
almost entirely occupied by already-compressed streams, so packing them again
would save little and would cost the property above.

## Rights

This repository redistributes third-party material. It grants no licence of its
own beyond what each upstream already grants; see [NOTICE](NOTICE). If you hold
rights to a file here and want it removed, open an issue.
