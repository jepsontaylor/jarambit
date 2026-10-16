import React, { useEffect, useMemo, useState } from 'react';
import { BatteryMatrixGrid } from './components/BatteryMatrixGrid';
import { CadViewer3D } from './components/CadViewer3D';
import { GateScorecardPanel } from './components/GateScorecardPanel';
import { WaveParetoChart } from './components/WaveParetoChart';
import { DEFAULT_STUDIO_BUNDLE } from './data/defaultDataset';
import type { MasterScorecard, ParsedMesh3D, WebStudioBundle } from './types';

export const App: React.FC = () => {
  const [bundle, setBundle] = useState<WebStudioBundle>(DEFAULT_STUDIO_BUNDLE);
  const [selectedSubject, setSelectedSubject] = useState<string>('w282_p14_c01');
  const [customMesh, setCustomMesh] = useState<ParsedMesh3D | null>(null);
  const [customScorecards, setCustomScorecards] = useState<Record<string, MasterScorecard>>({});

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const resp = await fetch('/data/index.json');
        if (!resp.ok) return;
        const json = (await resp.json()) as WebStudioBundle;
        if (!cancelled && json?.schema === 'jarambit.web_studio_bundle.v1') {
          setBundle(json);
        }
      } catch {
        // Offline or Vitest environment: DEFAULT_STUDIO_BUNDLE is already active
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const catalogIds = useMemo(
    () => new Set(bundle.subjects.map((s) => s.id)),
    [bundle.subjects],
  );

  const activeScorecard: MasterScorecard | null =
    customScorecards[selectedSubject] ??
    bundle.featured_scorecards[selectedSubject] ??
    null;

  const activeBatteryRecord =
    activeScorecard?.cad_battery ??
    bundle.battery_records[selectedSubject] ??
    null;

  const handleSelectSubject = (subjId: string) => {
    setCustomMesh(null);
    setSelectedSubject(subjId);
  };

  const handleUploadScorecard = (sc: MasterScorecard) => {
    const id = sc.subject || 'uploaded_cad';
    setCustomScorecards((prev) => ({ ...prev, [id]: sc }));
    setSelectedSubject(id);
  };

  const featuredQuickLinks = [
    { id: 'w282_p14_c01', tag: '75.32g Record Ultralight' },
    { id: 'w282_p10_c02', tag: 'Top W_CAD_v2 (+1.7978)' },
    { id: 'w281_s2932_c01', tag: 'w281 Leader (75.70g)' },
    { id: 'w280_s2931_c01', tag: 'w280 Leader (75.82g)' },
    { id: 'c10a', tag: 'Switchback C10a STEP' },
  ];

  return (
    <div className="studio-shell">
      <header className="studio-topbar">
        <div className="brand-block">
          <div className="brand-badge">JARAMBIT</div>
          <div>
            <h1>3D CAD & Multi-Solver Gate Scorecard Studio</h1>
            <p className="subtitle">
              Pure-Rust B-Rep STEP/STL Manifold · CST+DKT Plate · Bore-Pin/Winkler Buckling (side.a4) · 3D TET10 Tip Submodel
            </p>
          </div>
        </div>

        <div className="topbar-actions">
          <div className="quick-pills" role="group" aria-label="Featured CAD Candidates">
            {featuredQuickLinks.map((item) => (
              <button
                key={item.id}
                type="button"
                className={`quick-pill ${selectedSubject === item.id ? 'active' : ''}`}
                onClick={() => handleSelectSubject(item.id)}
              >
                <strong>{item.id}</strong>
                <span>{item.tag}</span>
              </button>
            ))}
          </div>

          <label className="subject-select-label">
            <span>All 21 Catalog Subjects:</span>
            <select
              aria-label="Select Catalog Subject"
              value={selectedSubject}
              onChange={(e) => handleSelectSubject(e.target.value)}
            >
              {bundle.subjects.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.id} ({s.pass_count}/18 pass · G1={s.g1_score != null ? s.g1_score.toFixed(4) : 'INC'})
                </option>
              ))}
              {Object.keys(customScorecards)
                .filter((k) => !catalogIds.has(k))
                .map((k) => (
                  <option key={k} value={k}>
                    {k} (Uploaded)
                  </option>
                ))}
            </select>
          </label>
        </div>
      </header>

      <main className="studio-main-grid">
        <div className="top-split-grid">
          <CadViewer3D
            subjectId={selectedSubject}
            scorecard={activeScorecard}
            customMesh={customMesh}
            onUploadMesh={(mesh) => setCustomMesh(mesh)}
            onUploadScorecard={handleUploadScorecard}
          />
          <GateScorecardPanel
            subjectId={selectedSubject}
            scorecard={activeScorecard}
            batteryRecord={activeBatteryRecord}
          />
        </div>

        <WaveParetoChart
          trajectory={bundle.wave_trajectory}
          catalogIds={catalogIds}
          selectedSubject={selectedSubject}
          onSelectSubject={handleSelectSubject}
        />

        <BatteryMatrixGrid
          caseIds={bundle.case_ids}
          subjects={bundle.subjects}
          batteryRecords={bundle.battery_records}
          selectedSubject={selectedSubject}
          onSelectSubject={handleSelectSubject}
        />
      </main>

      <footer className="studio-footer">
        <code>cargo run --release -p jarambit -- score-cad w282_p14_c01</code>
        <span>·</span>
        <code>cargo run --release -p jarambit -- cad-battery</code>
        <span>·</span>
        <code>cargo run --release -p jarambit -- export-web-data --out-dir web/public/data</code>
      </footer>
    </div>
  );
};

export default App;
