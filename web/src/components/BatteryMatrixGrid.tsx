import React, { useState } from 'react';
import type { BatteryCase, CadBatteryRecord, SubjectSummary } from '../types';

interface BatteryMatrixGridProps {
  caseIds: string[];
  subjects: SubjectSummary[];
  batteryRecords: Record<string, CadBatteryRecord>;
  selectedSubject: string;
  onSelectSubject: (subjectId: string) => void;
}

export const BatteryMatrixGrid: React.FC<BatteryMatrixGridProps> = ({
  caseIds,
  subjects,
  batteryRecords,
  selectedSubject,
  onSelectSubject,
}) => {
  const [selectedCaseId, setSelectedCaseId] = useState<string>('solid.tip');

  const activeRecord = batteryRecords[selectedSubject];
  const inspectedCase: BatteryCase | undefined = activeRecord?.cases.find(
    (c) => c.id === selectedCaseId,
  );

  const totalCells = subjects.length * caseIds.length;
  const totalPass = subjects.reduce((acc, s) => acc + s.pass_count, 0);

  return (
    <section className="studio-card battery-matrix-panel" aria-label="21x18 CAD Evaluator Battery Matrix">
      <div className="panel-header">
        <div>
          <span className="eyebrow">21 SUBJECTS × 18 EVALUATORS ({totalCells} CELLS)</span>
          <h2>
            Full CAD Evaluator Battery Matrix{' '}
            <span className="badge badge-neutral">
              {totalPass}/{totalCells} PASS ACROSS CATALOG
            </span>
          </h2>
        </div>

        <div className="legend-strip">
          <span className="legend-item">
            <i className="dot pass" /> pass
          </span>
          <span className="legend-item">
            <i className="dot fail" /> fail
          </span>
          <span className="legend-item">
            <i className="dot incomplete" /> incomplete
          </span>
          <span className="legend-item">
            <i className="dot blocked" /> blocked
          </span>
        </div>
      </div>

      <div className="matrix-scroll-container">
        <table className="battery-matrix-table">
          <thead>
            <tr>
              <th className="sticky-col">Subject</th>
              <th>Kind</th>
              <th>Pass</th>
              <th>G1</th>
              {caseIds.map((cid) => (
                <th
                  key={cid}
                  className={`rot-header ${selectedCaseId === cid ? 'active-col' : ''}`}
                  onClick={() => setSelectedCaseId(cid)}
                  title={cid}
                >
                  <span>{cid}</span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {subjects.map((subj) => {
              const rec = batteryRecords[subj.id];
              const isSelected = subj.id === selectedSubject;
              const caseMap = new Map<string, BatteryCase>();
              rec?.cases.forEach((c) => caseMap.set(c.id, c));

              return (
                <tr
                  key={subj.id}
                  className={isSelected ? 'selected-row' : ''}
                  onClick={() => onSelectSubject(subj.id)}
                >
                  <td className="sticky-col subject-cell">
                    <strong>{subj.id}</strong>
                    {subj.has_stl && <span className="stl-tag">3D</span>}
                  </td>
                  <td className="mono-cell muted">
                    {subj.kind === 'native_step' ? 'STEP' : 'Genome'}
                  </td>
                  <td className="mono-cell">
                    {subj.pass_count}/{caseIds.length}
                  </td>
                  <td className="mono-cell">
                    {subj.g1_score != null ? subj.g1_score.toFixed(4) : '—'}
                  </td>
                  {caseIds.map((cid) => {
                    const c = caseMap.get(cid);
                    const st = c?.status ?? 'incomplete';
                    const isCellActive = isSelected && selectedCaseId === cid;
                    return (
                      <td
                        key={cid}
                        className={`matrix-cell ${st} ${isCellActive ? 'active-cell' : ''}`}
                        onClick={(e) => {
                          e.stopPropagation();
                          onSelectSubject(subj.id);
                          setSelectedCaseId(cid);
                        }}
                        title={`${subj.id} · ${cid}: ${st}`}
                      >
                        <span className="cell-glyph">
                          {st === 'pass'
                            ? '✓'
                            : st === 'fail'
                              ? '✗'
                              : st === 'blocked'
                                ? '⊘'
                                : '·'}
                        </span>
                      </td>
                    );
                  })}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {inspectedCase && (
        <div className="case-inspector-drawer" aria-label="Inspected Evaluator Case Detail">
          <div className="drawer-head">
            <div>
              <span className="eyebrow">SELECTED CELL EVIDENCE</span>
              <h3>
                {selectedSubject} → <code>{inspectedCase.id}</code>{' '}
                <span className={`status-chip ${inspectedCase.status}`}>
                  {inspectedCase.status.toUpperCase()}
                </span>
              </h3>
            </div>
            <div className="drawer-meta">
              <span>Kind: <code>{inspectedCase.kind}</code></span>
              <span>Solver: <code>{inspectedCase.solver ?? 'contract'}</code></span>
              {inspectedCase.evidence_path && (
                <span>Evidence: <code>{inspectedCase.evidence_path}</code></span>
              )}
            </div>
          </div>
          {inspectedCase.reason && (
            <p className="drawer-reason">Reason: {inspectedCase.reason}</p>
          )}
          {inspectedCase.detail && (
            <pre className="drawer-json">
              {JSON.stringify(inspectedCase.detail, null, 2)}
            </pre>
          )}
        </div>
      )}
    </section>
  );
};
