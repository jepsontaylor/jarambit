# finishlib — automated per-CAD metallic finish pipeline

    python3 finishlib/run_finishes.py --bundle MESH/bundle.json [--regions MESH/regions.json] \
        --out OUT [--finishes all | id ...] [--res 1920 1080] [--spp 256] [--device CPU|OPTIX]
    python3 finishlib/run_finishes.py --cad part.step --out OUT        # ingest.py first

1. `blade_mask.py` — zones per face: coat | blade_flat | bevel | edge_apex | serration. Labels (ddc9a30
   B-rep region_id) when present, always cross-checked against a geometric detector (thin-section apex +
   grind faces connected to it); geometric hits the labels missed are unioned in as BARE. Blade flats =
   footprint pixels sandwiched between the grinds + 0.6 mm guard band. Arc params s,t follow the knife
   centre-curve. Validation checks → exit 3 on failure. `blade_mask_2d.png` + a 3-D zone render.
2. `thinfilm.py` — spectral Airy TiO2-on-Ti LUT (CIE CMF), because Blender 4.2 thin film does not act on
   the metallic lobe. Shader samples it at d·cosθt (view-angle hue shift).
3. `finishes.yaml` — declarative library (layers/film/pattern/micro/edge_wear/cavity/clearcoat).
4. `blender_finish.py` — worker hook (request.finish_library); coat only on zone 0, bare house finishes on
   zones 1-4, material_index read-back assertion.
Camera/rig: lookdev.build_request(hero_3q) unchanged. GPU: waits for idle + flock; CPU mode is niced.
