import React, { useState } from 'react';
import type { WaveTrajectoryPoint } from '../types';

interface WaveParetoChartProps {
  trajectory: WaveTrajectoryPoint[];
  catalogIds: Set<string>;
  selectedSubject: string;
  onSelectSubject: (subjectId: string) => void;
}

export const WaveParetoChart: React.FC<WaveParetoChartProps> = ({
  trajectory,
  catalogIds,
  selectedSubject,
  onSelectSubject,
}) => {
  const [viewMode, setViewMode] = useState<'trajectory' | 'pareto'>('trajectory');

  const width = 760;
  const height = 250;
  const padL = 56;
  const padR = 52;
  const padT = 26;
  const padB = 42;
  const plotW = width - padL - padR;
  const plotH = height - padT - padB;

  const feasiblePoints = trajectory.filter((p) => p.w_cad > 0);
  const minMass = 74.5;
  const maxMass = 92.5;
  const minG1 = 0.72;
  const maxG1 = 0.90;

  const xForIdx = (i: number) =>
    padL + (i / Math.max(1, trajectory.length - 1)) * plotW;
  const yForMass = (m: number) =>
    padT + ((maxMass - m) / (maxMass - minMass)) * plotH;
  const yForG1 = (g: number) =>
    padT + ((maxG1 - g) / (maxG1 - minG1)) * plotH;

  const massPolyline = trajectory
    .map((pt, i) => `${xForIdx(i).toFixed(1)},${yForMass(pt.mass_3d_g).toFixed(1)}`)
    .join(' ');
  const g1Polyline = trajectory
    .map((pt, i) => `${xForIdx(i).toFixed(1)},${yForG1(pt.g1).toFixed(1)}`)
    .join(' ');

  return (
    <section className="studio-card wave-chart-panel" aria-label="Cross-Wave Evolution and Pareto Trajectory">
      <div className="panel-header">
        <div>
          <span className="eyebrow">EVOLUTIONARY TRAJECTORY (W20 → W282)</span>
          <h2>
            Mass Reduction (−17.7%) & Combined Fitness Climb
          </h2>
        </div>

        <div className="viewer-controls">
          <button
            type="button"
            className={`mode-btn ${viewMode === 'trajectory' ? 'active' : ''}`}
            onClick={() => setViewMode('trajectory')}
          >
            Wave Trajectory (w20→w282)
          </button>
          <button
            type="button"
            className={`mode-btn ${viewMode === 'pareto' ? 'active' : ''}`}
            onClick={() => setViewMode('pareto')}
          >
            Mass vs W_CAD_v2 Pareto
          </button>
        </div>
      </div>

      {viewMode === 'trajectory' ? (
        <div className="svg-chart-wrap">
          <svg
            viewBox={`0 0 ${width} ${height}`}
            className="trajectory-svg"
            role="img"
            aria-label="Wave mass and G1 fitness evolution chart"
          >
            {[75, 80, 85, 90].map((m) => {
              const y = yForMass(m);
              return (
                <g key={m}>
                  <line
                    x1={padL}
                    y1={y}
                    x2={width - padR}
                    y2={y}
                    stroke="rgba(148,163,184,0.14)"
                    strokeDasharray="3 3"
                  />
                  <text x={padL - 8} y={y + 4} textAnchor="end" className="axis-label-left">
                    {m}g
                  </text>
                </g>
              );
            })}

            <polyline
              fill="none"
              stroke="#38bdf8"
              strokeWidth="2.5"
              points={massPolyline}
            />
            <polyline
              fill="none"
              stroke="#22c55e"
              strokeWidth="2.2"
              strokeDasharray="5 3"
              points={g1Polyline}
            />

            {trajectory.map((pt, i) => {
              const cx = xForIdx(i);
              const cyM = yForMass(pt.mass_3d_g);
              const cyG = yForG1(pt.g1);
              const isSelected = pt.subject === selectedSubject;
              const isClickable = catalogIds.has(pt.subject);
              return (
                <g
                  key={pt.wave}
                  className={isClickable ? 'clickable-node' : ''}
                  onClick={() => {
                    if (isClickable) onSelectSubject(pt.subject);
                  }}
                >
                  <circle
                    cx={cx}
                    cy={cyM}
                    r={isSelected ? 6 : 4}
                    fill={isSelected ? '#f8fafc' : '#38bdf8'}
                    stroke="#0f172a"
                    strokeWidth="1.5"
                  >
                    <title>
                      {`${pt.wave} (${pt.subject}): 3D Mass ${pt.mass_3d_g.toFixed(3)} g, W_CAD ${pt.w_cad.toFixed(4)}, G1 ${pt.g1.toFixed(4)}`}
                    </title>
                  </circle>
                  <circle
                    cx={cx}
                    cy={cyG}
                    r={isSelected ? 5.5 : 3.5}
                    fill={pt.w_cad > 0 ? '#22c55e' : '#ef4444'}
                  />
                  {i % 2 === 0 || i === trajectory.length - 1 ? (
                    <text
                      x={cx}
                      y={height - 12}
                      textAnchor="middle"
                      className="axis-label-bottom"
                    >
                      {pt.wave.replace(' (record)', '*').replace(' (peer)', '')}
                    </text>
                  ) : null}
                </g>
              );
            })}
          </svg>
          <div className="chart-caption">
            <span>
              <i className="dot" style={{ background: '#38bdf8' }} /> 3D CAD Mass (g) — Left Axis
            </span>
            <span>
              <i className="dot" style={{ background: '#22c55e' }} /> Global Fitness G1 — Right Trend
            </span>
            <span>
              Record Ultralight: <strong>w282_p14_c01 (75.323 g 3D / 75.568 g plate)</strong> · Top
              W_CAD_v2: <strong>w282_p10_c02 (+1.797848)</strong>
            </span>
          </div>
        </div>
      ) : (
        <div className="svg-chart-wrap">
          <svg
            viewBox={`0 0 ${width} ${height}`}
            className="trajectory-svg"
            role="img"
            aria-label="Pareto front of 3D Mass vs W_CAD_v2 score"
          >
            {feasiblePoints.map((pt) => {
              const x = padL + ((92.0 - pt.mass_3d_g) / (92.0 - 74.8)) * plotW;
              const y = padT + ((1.82 - pt.w_cad) / (1.82 - 1.15)) * plotH;
              const isSelected = pt.subject === selectedSubject;
              const isClickable = catalogIds.has(pt.subject);
              return (
                <g
                  key={pt.subject}
                  className={isClickable ? 'clickable-node' : ''}
                  onClick={() => {
                    if (isClickable) onSelectSubject(pt.subject);
                  }}
                >
                  <circle
                    cx={x}
                    cy={y}
                    r={isSelected ? 7 : 5}
                    fill={isSelected ? '#f59e0b' : '#38bdf8'}
                    stroke="#0f172a"
                    strokeWidth="1.5"
                  />
                  <text x={x + 8} y={y + 4} className="node-tag">
                    {pt.wave} ({pt.mass_3d_g.toFixed(2)}g)
                  </text>
                </g>
              );
            })}
          </svg>
          <div className="chart-caption">
            <span>Horizontal: Lighter Mass (Right is Lighter)</span>
            <span>Vertical: Higher W_CAD_v2 Combined Score (Up is Better)</span>
          </div>
        </div>
      )}
    </section>
  );
};
