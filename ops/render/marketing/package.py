"""Release staging. Writes a manifest and SHA256SUMS. Does not upload.

The caption is fixed. art_review stays pending. Raw EXR paths under the
staging root are removed after a successful package unless keep_raw is set.
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import canon

SCHEMA = "jarambit.render.marketing.v1"
CAPTION = "physically based visualization under stated material assumptions"
PRODUCT = "SWITCHBACK-class titanium hiking/utility karambit"
BANNED = (
    "combat",
    "tactical",
    "weapon",
    "military",
    "self-defense",
    "self defence",
    "fighting",
)


class PackageError(RuntimeError):
    pass


def banned_hits(text):
    lowered = text.lower()
    return [word for word in BANNED if word in lowered]


def readme_snippet(manifest) -> str:
    source = manifest["source_cad"]["sha256"]
    lines = [
        "## Renders",
        "",
        f"{PRODUCT}. {CAPTION}.",
        "",
        f"Source CAD sha256 `{source}`. Plan `{manifest['plan_key']}`.",
        "Large files are release assets. This tree keeps the manifest and the small preview only.",
        "art_review: pending.",
        "",
    ]
    for item in manifest["outputs"]:
        lines.append(f"- `{item['path']}` `{item['sha256']}`")
    text = "\n".join(lines) + "\n"
    hits = banned_hits(text)
    if hits:
        raise PackageError(f"snippet contains banned wording: {hits}")
    return text


def _rel(root, path):
    return os.path.relpath(path, root)


def verify_source(cad_path, expected_sha256):
    if not cad_path or not os.path.isfile(cad_path):
        return {"path": cad_path, "sha256": expected_sha256, "verified": False}
    actual = canon.sha256_file(cad_path)
    return {
        "path": cad_path,
        "sha256": actual,
        "verified": actual == expected_sha256,
    }


def build_manifest(*, source_cad, mesh_bundle_sha256, toolchain, git_sha, plan_key,
                   outputs, normal_policy=None):
    if not source_cad.get("verified"):
        raise PackageError("source CAD sha256 did not verify; refusing to stage a manifest")
    if not mesh_bundle_sha256 or not git_sha or not plan_key:
        raise PackageError("manifest needs bundle sha, git sha and plan key")
    if not outputs:
        raise PackageError("manifest needs at least one output")
    manifest = {
        "schema": SCHEMA,
        "product": PRODUCT,
        "caption": CAPTION,
        "appearance": "appearance_assumed",
        "art_review": "pending",
        "source_cad": {
            "path": source_cad.get("path"),
            "sha256": source_cad["sha256"],
            "verified": True,
        },
        "mesh_bundle_sha256": mesh_bundle_sha256,
        "normal_policy": normal_policy,
        "toolchain": toolchain,
        "git_sha": git_sha,
        "plan_key": plan_key,
        "outputs": outputs,
    }
    return manifest


def write_sums(root, paths):
    lines = []
    for path in paths:
        rel = _rel(root, path).replace(os.sep, "/")
        lines.append(f"{canon.sha256_file(path)}  {rel}")
    lines.sort(key=lambda line: line.split("  ", 1)[1])
    text = "\n".join(lines) + "\n"
    dest = os.path.join(root, "SHA256SUMS")
    canon.atomic_write_text(dest, text)
    return dest


def verify_sums(root) -> bool:
    sums = os.path.join(root, "SHA256SUMS")
    if not os.path.isfile(sums):
        return False
    with open(sums, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            digest, rel = line.split("  ", 1)
            path = os.path.join(root, rel)
            if not os.path.isfile(path) or canon.sha256_file(path) != digest:
                return False
    return True


def output_record(root, path, role):
    return {"path": _rel(root, path).replace(os.sep, "/"), "sha256": canon.sha256_file(path), "role": role}


def purge_raw(root, raw_paths, keep_raw=False):
    """Delete raw EXR files that live under root. Denoised files are not in raw_paths."""
    if keep_raw:
        return []
    root_real = os.path.realpath(root)
    removed = []
    for path in raw_paths:
        if not path or not os.path.isfile(path):
            continue
        real = os.path.realpath(path)
        if os.path.commonpath([root_real, real]) != root_real:
            raise PackageError(f"refusing to delete outside the staging root: {path}")
        if not real.endswith(".exr"):
            raise PackageError(f"refusing to delete a non-EXR as raw: {path}")
        os.remove(real)
        removed.append(real)
    return removed


def stage(root, *, cad_path, expected_cad_sha256, mesh_bundle_sha256, toolchain, git_sha,
          plan_key, files, normal_policy=None, raw_paths=None, keep_raw=False):
    """files is a list of {src, dest_name, role}. Copies into root, then writes manifest and sums.

    The manifest and the snippet are hashed into SHA256SUMS. Raw EXR purge runs
    only after those files are in place.
    """
    os.makedirs(root, exist_ok=True)
    source = verify_source(cad_path, expected_cad_sha256)
    records = []
    written = []
    for item in files:
        dest = os.path.join(root, item["dest_name"])
        os.makedirs(os.path.dirname(dest) or root, exist_ok=True)
        with open(item["src"], "rb") as src, open(dest + ".tmp", "wb") as out:
            data = src.read()
            out.write(data)
            out.flush()
            os.fsync(out.fileno())
        os.replace(dest + ".tmp", dest)
        records.append(output_record(root, dest, item["role"]))
        written.append(dest)
    manifest = build_manifest(
        source_cad=source,
        mesh_bundle_sha256=mesh_bundle_sha256,
        toolchain=toolchain,
        git_sha=git_sha,
        plan_key=plan_key,
        outputs=records,
        normal_policy=normal_policy,
    )
    manifest_path = os.path.join(root, "manifest.marketing.json")
    canon.atomic_write_json(manifest_path, manifest)
    snippet = readme_snippet(manifest)
    snippet_path = os.path.join(root, "README_SNIPPET.md")
    canon.atomic_write_text(snippet_path, snippet)
    # Sums cover the deliveries, the manifest and the snippet. Not themselves.
    write_sums(root, written + [manifest_path, snippet_path])
    if not verify_sums(root):
        raise PackageError("SHA256SUMS failed to verify immediately after write")
    removed = purge_raw(root, raw_paths or [], keep_raw=keep_raw)
    return {"manifest": manifest_path, "sums": os.path.join(root, "SHA256SUMS"),
            "snippet": snippet_path, "purged_raw": removed}
