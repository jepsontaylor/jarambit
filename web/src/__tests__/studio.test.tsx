import { renderToString } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import { App } from '../App';
import { BatteryMatrixGrid } from '../components/BatteryMatrixGrid';
import { buildParametricKarambitMesh, CadViewer3D } from '../components/CadViewer3D';
import { GateScorecardPanel } from '../components/GateScorecardPanel';
import { WaveParetoChart } from '../components/WaveParetoChart';
import { DEFAULT_STUDIO_BUNDLE } from '../data/defaultDataset';
import { parseStepFacetedMesh, parseStlMesh } from '../utils/stlParser';

describe('Jarambit 3D CAD & Gate Scorecard Studio', () => {
  it('contains all 23 catalog subjects and 18 evaluator cases (414 cells) in DEFAULT_STUDIO_BUNDLE', () => {
    expect(DEFAULT_STUDIO_BUNDLE.schema).toBe('jarambit.web_studio_bundle.v1');
    expect(DEFAULT_STUDIO_BUNDLE.case_ids).toHaveLength(18);
    expect(DEFAULT_STUDIO_BUNDLE.subjects).toHaveLength(23);

    const w283 = DEFAULT_STUDIO_BUNDLE.featured_scorecards.w283_p14_c01;
    expect(w283).toBeDefined();
    expect(w283.weighted_cad_score.all_engineering_gates_pass).toBe(true);
    expect(w283.weighted_cad_score.W_CAD).toBeCloseTo(1.795572, 4);
    expect(w283.global_fitness_G1.G).toBeCloseTo(0.913855, 5);
    expect(w283.cad.watertight_exact).toBe(true);
    expect(w283.cad.mass_3d_g).toBeCloseTo(75.199, 2);

    const w282 = DEFAULT_STUDIO_BUNDLE.featured_scorecards.w282_p14_c01;
    expect(w282).toBeDefined();
    expect(w282.weighted_cad_score.all_engineering_gates_pass).toBe(true);
    expect(w282.weighted_cad_score.W_CAD).toBeCloseTo(1.779046, 5);
    expect(w282.global_fitness_G1.G).toBeCloseTo(0.87821, 5);
    expect(w282.cad.watertight_exact).toBe(true);
    expect(w282.cad.mass_3d_g).toBeCloseTo(75.323, 2);
  });

  it('parses ASCII STL and STEP faceted meshes and computes watertight 2-manifold census', () => {
    const asciiStl = `solid tet
  facet normal 0 0 -1
    outer loop
      vertex 0 0 0
      vertex 0 10 0
      vertex 10 0 0
    endloop
  endfacet
  facet normal 0 -1 0
    outer loop
      vertex 0 0 0
      vertex 10 0 0
      vertex 0 0 10
    endloop
  endfacet
  facet normal -1 0 0
    outer loop
      vertex 0 0 0
      vertex 0 0 10
      vertex 0 10 0
    endloop
  endfacet
  facet normal 0.577 0.577 0.577
    outer loop
      vertex 10 0 0
      vertex 0 10 0
      vertex 0 0 10
    endloop
  endfacet
endsolid tet`;
    const enc = new TextEncoder().encode(asciiStl);
    const mesh = parseStlMesh(enc.buffer, 'tet.stl');
    expect(mesh.facets).toBe(4);
    expect(mesh.boundaryEdges).toBe(0);
    expect(mesh.nonManifoldEdges).toBe(0);
    expect(mesh.watertightExact).toBe(true);
    expect(mesh.volumeMm3).toBeCloseTo(166.7, 1);

    const stepText = `ISO-10303-21;
DATA;
#1 = CARTESIAN_POINT('',(0.0,0.0,0.0));
#2 = CARTESIAN_POINT('',(0.0,10.0,0.0));
#3 = CARTESIAN_POINT('',(10.0,0.0,0.0));
#4 = CARTESIAN_POINT('',(0.0,0.0,10.0));
#10 = POLY_LOOP('',(#1,#2,#3));
#11 = POLY_LOOP('',(#1,#3,#4));
#12 = POLY_LOOP('',(#1,#4,#2));
#13 = POLY_LOOP('',(#3,#2,#4));
ENDSEC;
END-ISO-10303-21;`;
    const stepMesh = parseStepFacetedMesh(stepText, 'tet.step');
    expect(stepMesh.facets).toBe(4);
    expect(stepMesh.watertightExact).toBe(true);
  });

  it('builds a watertight parametric karambit preview mesh', () => {
    const mesh = buildParametricKarambitMesh('w282_p14_c01.stl');
    expect(mesh.facets).toBeGreaterThan(200);
    expect(mesh.watertightExact).toBe(true);
    expect(mesh.mass3dG).toBeCloseTo(75.323, 3);
  });

  it('renders App, GateScorecardPanel, BatteryMatrixGrid, WaveParetoChart, and CadViewer3D', () => {
    const appHtml = renderToString(<App />);
    expect(appHtml).toContain('3D CAD &amp; Multi-Solver Gate Scorecard Studio');
    expect(appHtml).toContain('ALL 16 GATES PASS');
    expect(appHtml).toContain('1.795575');
    expect(appHtml).toContain('0.913855');

    const peerSc = DEFAULT_STUDIO_BUNDLE.featured_scorecards.w283_p10_c02;
    const peerHtml = renderToString(
      <GateScorecardPanel
        subjectId="w283_p10_c02"
        scorecard={peerSc}
        batteryRecord={peerSc.cad_battery}
      />,
    );
    expect(peerHtml).toContain('1.816593');
    expect(peerHtml).toContain('0.916719');

    const c10aSc = DEFAULT_STUDIO_BUNDLE.featured_scorecards.c10a;
    const c10aHtml = renderToString(
      <CadViewer3D
        subjectId="c10a"
        scorecard={c10aSc}
        customMesh={null}
        onUploadMesh={() => {}}
        onUploadScorecard={() => {}}
      />,
    );
    expect(c10aHtml).toContain('WATERTIGHT 2-MANIFOLD');

    const matrixHtml = renderToString(
      <BatteryMatrixGrid
        caseIds={DEFAULT_STUDIO_BUNDLE.case_ids}
        subjects={DEFAULT_STUDIO_BUNDLE.subjects}
        batteryRecords={DEFAULT_STUDIO_BUNDLE.battery_records}
        selectedSubject="w282_p14_c01"
        onSelectSubject={() => {}}
      />,
    );
    expect(matrixHtml).toContain('Full CAD Evaluator Battery Matrix');
    expect(matrixHtml).toContain('solid.tip');

    const chartHtml = renderToString(
      <WaveParetoChart
        trajectory={DEFAULT_STUDIO_BUNDLE.wave_trajectory}
        catalogIds={new Set(DEFAULT_STUDIO_BUNDLE.subjects.map((s) => s.id))}
        selectedSubject="w282_p14_c01"
        onSelectSubject={() => {}}
      />,
    );
    expect(chartHtml).toContain('Mass Reduction');
  });
});
