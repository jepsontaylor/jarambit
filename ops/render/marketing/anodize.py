"""Generate finish presets for the Ti anodize family: presets/finish_ti64_anodize_<color>.json.

    python3 ops/render/marketing/anodize.py            # (re)write all, deterministic
    python3 ops/render/marketing/anodize.py --check    # fail if any generated file is stale
"""
import copy
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PRESETS = os.path.join(HERE, "presets")


def build(family, base, color):
    spec = family["colors"][color]
    out = copy.deepcopy(base)
    out["name"] = f"finish_ti64_anodize_{color}"
    out["family"] = {"name": family["name"], "color": color, **{k: v for k, v in spec.items()}}
    fin = f"anodize_{color}"
    kind = spec.get("kind", "anodize")
    if kind == "raw":
        fspec = copy.deepcopy(base["finishes"][spec["finish"]])
    elif kind == "coating":
        fspec = dict(family["film_base"], roughness=spec["roughness"])
        out["region_metal"] = {r: {"base_color_lin": spec["base_color_lin"], "f82_tint": spec["base_color_lin"]}
                               for r in family["anodized_regions"]}
    else:
        fspec = dict(family["film_base"], thin_film_nm=float(spec["thin_film_nm"]), thin_film_ior=family["film_ior"])
    out["finishes"][fin] = fspec
    for r in family["anodized_regions"]:
        out["default_assignment"][r] = fin
    out["note"] = base["note"] + " " + family["note"]
    return out


def main(argv=None):
    argv = argv or sys.argv[1:]
    family = json.load(open(os.path.join(PRESETS, "anodize_family.json")))
    base = json.load(open(os.path.join(PRESETS, family["base"] + ".json")))
    stale = []
    for color in sorted(family["colors"]):
        path = os.path.join(PRESETS, f"finish_ti64_anodize_{color}.json")
        text = json.dumps(build(family, base, color), indent=1, sort_keys=True) + "\n"
        if "--check" in argv:
            if not os.path.isfile(path) or open(path).read() != text:
                stale.append(path)
            continue
        open(path, "w").write(text)
    if stale:
        print("stale:", stale)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
