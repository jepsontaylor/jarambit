import { ParsedMesh3D } from '../types';

const TI64_DENSITY_G_PER_MM3 = 0.00443;

function quantizeCoord(x: number): number {
  return Math.round(x * 10000);
}

export function buildParsedMeshFromRawTriangles(
  name: string,
  rawTris: [[number, number, number], [number, number, number], [number, number, number]][],
): ParsedMesh3D {
  const vertMap = new Map<string, number>();
  const vertices: [number, number, number][] = [];
  const triangles: [number, number, number][] = [];
  const normals: [number, number, number][] = [];

  for (const [p0, p1, p2] of rawTris) {
    const idx = [p0, p1, p2].map((pt) => {
      const k = `${quantizeCoord(pt[0])},${quantizeCoord(pt[1])},${quantizeCoord(pt[2])}`;
      const existing = vertMap.get(k);
      if (existing !== undefined) {
        return existing;
      }
      const next = vertices.length;
      vertices.push([pt[0], pt[1], pt[2]]);
      vertMap.set(k, next);
      return next;
    }) as [number, number, number];

    if (idx[0] === idx[1] || idx[1] === idx[2] || idx[2] === idx[0]) {
      continue;
    }
    triangles.push(idx);

    const ux = p1[0] - p0[0];
    const uy = p1[1] - p0[1];
    const uz = p1[2] - p0[2];
    const vx = p2[0] - p0[0];
    const vy = p2[1] - p0[1];
    const vz = p2[2] - p0[2];
    const nx = uy * vz - uz * vy;
    const ny = uz * vx - ux * vz;
    const nz = ux * vy - uy * vx;
    const len = Math.hypot(nx, ny, nz) || 1;
    normals.push([nx / len, ny / len, nz / len]);
  }

  // Edge census + signed tetrahedral volume
  const directedCounts = new Map<string, number>();
  const undirectedKeys = new Set<string>();
  let signedVol6 = 0;

  for (const [i0, i1, i2] of triangles) {
    const e01 = `${i0}->${i1}`;
    const e12 = `${i1}->${i2}`;
    const e20 = `${i2}->${i0}`;
    directedCounts.set(e01, (directedCounts.get(e01) ?? 0) + 1);
    directedCounts.set(e12, (directedCounts.get(e12) ?? 0) + 1);
    directedCounts.set(e20, (directedCounts.get(e20) ?? 0) + 1);

    undirectedKeys.add(i0 < i1 ? `${i0}:${i1}` : `${i1}:${i0}`);
    undirectedKeys.add(i1 < i2 ? `${i1}:${i2}` : `${i2}:${i1}`);
    undirectedKeys.add(i2 < i0 ? `${i2}:${i0}` : `${i0}:${i2}`);

    const a = vertices[i0];
    const b = vertices[i1];
    const c = vertices[i2];
    signedVol6 +=
      a[0] * (b[1] * c[2] - b[2] * c[1]) -
      a[1] * (b[0] * c[2] - b[2] * c[0]) +
      a[2] * (b[0] * c[1] - b[1] * c[0]);
  }

  let maxDirectedRepeat = 0;
  for (const c of directedCounts.values()) {
    if (c > maxDirectedRepeat) maxDirectedRepeat = c;
  }

  let boundaryEdges = 0;
  let nonManifoldEdges = 0;
  for (const uk of undirectedKeys) {
    const [uStr, vStr] = uk.split(':');
    const cFwd = directedCounts.get(`${uStr}->${vStr}`) ?? 0;
    const cRev = directedCounts.get(`${vStr}->${uStr}`) ?? 0;
    const tot = cFwd + cRev;
    if (tot === 1) {
      boundaryEdges += 1;
    } else if (tot !== 2 || cFwd !== 1 || cRev !== 1) {
      nonManifoldEdges += 1;
    }
  }

  const bboxMin: [number, number, number] = [Infinity, Infinity, Infinity];
  const bboxMax: [number, number, number] = [-Infinity, -Infinity, -Infinity];
  let tipPoint: [number, number, number] = [0, 0, 0];
  let maxX = -Infinity;

  for (const v of vertices) {
    for (let d = 0; d < 3; d++) {
      if (v[d] < bboxMin[d]) bboxMin[d] = v[d];
      if (v[d] > bboxMax[d]) bboxMax[d] = v[d];
    }
    if (v[0] > maxX) {
      maxX = v[0];
      tipPoint = [v[0], v[1], v[2]];
    }
  }
  if (vertices.length === 0) {
    bboxMin.fill(0);
    bboxMax.fill(0);
  }

  const volumeMm3 = Math.abs(signedVol6) / 6.0;
  const mass3dG = Number((volumeMm3 * TI64_DENSITY_G_PER_MM3).toFixed(4));
  const watertightExact =
    triangles.length > 0 &&
    boundaryEdges === 0 &&
    nonManifoldEdges === 0 &&
    maxDirectedRepeat === 1;

  return {
    name,
    vertices,
    triangles,
    normals,
    facets: triangles.length,
    boundaryEdges,
    nonManifoldEdges,
    maxDirectedRepeat,
    watertightExact,
    volumeMm3: Number(volumeMm3.toFixed(2)),
    mass3dG,
    bboxMin,
    bboxMax,
    tipPoint,
  };
}

export function parseStlBuffer(buffer: ArrayBuffer, name = 'mesh.stl'): ParsedMesh3D {
  const bytes = new Uint8Array(buffer);
  if (bytes.byteLength >= 84) {
    const view = new DataView(buffer);
    const nTri = view.getUint32(80, true);
    if (84 + nTri * 50 === bytes.byteLength && nTri > 0) {
      const rawTris: [
        [number, number, number],
        [number, number, number],
        [number, number, number],
      ][] = [];
      for (let i = 0; i < nTri; i++) {
        const off = 84 + i * 50;
        const p0: [number, number, number] = [
          view.getFloat32(off + 12, true),
          view.getFloat32(off + 16, true),
          view.getFloat32(off + 20, true),
        ];
        const p1: [number, number, number] = [
          view.getFloat32(off + 24, true),
          view.getFloat32(off + 28, true),
          view.getFloat32(off + 32, true),
        ];
        const p2: [number, number, number] = [
          view.getFloat32(off + 36, true),
          view.getFloat32(off + 40, true),
          view.getFloat32(off + 44, true),
        ];
        rawTris.push([p0, p1, p2]);
      }
      return buildParsedMeshFromRawTriangles(name, rawTris);
    }
  }

  const text = new TextDecoder('utf-8').decode(bytes);
  return parseAsciiStlText(text, name);
}

export function parseAsciiStlText(text: string, name = 'mesh.stl'): ParsedMesh3D {
  const verts: [number, number, number][] = [];
  for (const rawLine of text.split(/\r?\n/)) {
    const line = rawLine.trim();
    if (line.toLowerCase().startsWith('vertex')) {
      const parts = line.split(/\s+/);
      if (parts.length >= 4) {
        const x = Number(parts[1]);
        const y = Number(parts[2]);
        const z = Number(parts[3]);
        if (Number.isFinite(x) && Number.isFinite(y) && Number.isFinite(z)) {
          verts.push([x, y, z]);
        }
      }
    }
  }
  const rawTris: [
    [number, number, number],
    [number, number, number],
    [number, number, number],
  ][] = [];
  for (let i = 0; i + 2 < verts.length; i += 3) {
    rawTris.push([verts[i], verts[i + 1], verts[i + 2]]);
  }
  return buildParsedMeshFromRawTriangles(name, rawTris);
}

export function parseStepText(text: string, name = 'mesh.step'): ParsedMesh3D {
  const cpMap = new Map<number, [number, number, number]>();
  const vpMap = new Map<number, number>();
  const deMap = new Map<number, [number, number]>();
  const elMap = new Map<number, [number, boolean][]>();

  const cpRegex = /#(\d+)\s*=\s*CARTESIAN_POINT\s*\([^,]*,\s*\(\s*([^)]+)\)\s*\)/g;
  let m: RegExpExecArray | null;
  while ((m = cpRegex.exec(text)) !== null) {
    const id = Number(m[1]);
    const nums = m[2].split(',').map((s) => Number(s.trim()));
    if (nums.length >= 3 && nums.every((n) => Number.isFinite(n))) {
      cpMap.set(id, [nums[0], nums[1], nums[2]]);
    }
  }

  const vpRegex = /#(\d+)\s*=\s*VERTEX_POINT\s*\([^,]*,\s*#(\d+)\s*\)/g;
  while ((m = vpRegex.exec(text)) !== null) {
    vpMap.set(Number(m[1]), Number(m[2]));
  }

  const deRegex = /#(\d+)\s*=\s*EDGE_CURVE\s*\([^,]*,\s*#(\d+)\s*,\s*#(\d+)/g;
  while ((m = deRegex.exec(text)) !== null) {
    deMap.set(Number(m[1]), [Number(m[2]), Number(m[3])]);
  }

  const oeMap = new Map<number, [number, boolean]>();
  const oeRegex = /#(\d+)\s*=\s*ORIENTED_EDGE\s*\([^,]*,[^,]*,[^,]*,\s*#(\d+)\s*,\s*\.(T|F)\.\s*\)/g;
  while ((m = oeRegex.exec(text)) !== null) {
    oeMap.set(Number(m[1]), [Number(m[2]), m[3] === 'T']);
  }

  const elRegex = /#(\d+)\s*=\s*EDGE_LOOP\s*\([^,]*,\s*\(\s*([^)]+)\)\s*\)/g;
  while ((m = elRegex.exec(text)) !== null) {
    const id = Number(m[1]);
    const refs = Array.from(m[2].matchAll(/#(\d+)/g)).map((r) => Number(r[1]));
    const items: [number, boolean][] = [];
    for (const r of refs) {
      const oe = oeMap.get(r);
      if (oe) items.push(oe);
    }
    elMap.set(id, items);
  }

  const rawTris: [
    [number, number, number],
    [number, number, number],
    [number, number, number],
  ][] = [];

  for (const items of elMap.values()) {
    const polyPts: [number, number, number][] = [];
    for (const [edgeId, sense] of items) {
      const edge = deMap.get(edgeId);
      if (!edge) continue;
      const vStart = sense ? edge[0] : edge[1];
      const cpId = vpMap.get(vStart) ?? vStart;
      const pt = cpMap.get(cpId);
      if (pt) polyPts.push(pt);
    }
    if (polyPts.length >= 3) {
      for (let k = 1; k + 1 < polyPts.length; k++) {
        rawTris.push([polyPts[0], polyPts[k], polyPts[k + 1]]);
      }
    }
  }

  const plRegex = /#(\d+)\s*=\s*POLY_LOOP\s*\([^,]*,\s*\(\s*([^)]+)\)\s*\)/g;
  while ((m = plRegex.exec(text)) !== null) {
    const refs = Array.from(m[2].matchAll(/#(\d+)/g)).map((r) => Number(r[1]));
    const polyPts: [number, number, number][] = [];
    for (const r of refs) {
      const cpId = vpMap.get(r) ?? r;
      const pt = cpMap.get(cpId);
      if (pt) polyPts.push(pt);
    }
    if (polyPts.length >= 3) {
      for (let k = 1; k + 1 < polyPts.length; k++) {
        rawTris.push([polyPts[0], polyPts[k], polyPts[k + 1]]);
      }
    }
  }

  return buildParsedMeshFromRawTriangles(name, rawTris);
}

export const parseStlMesh = parseStlBuffer;
export const parseStepFacetedMesh = parseStepText;

/**
 * Generates a watertight 3D karambit preview mesh (ring + grip + curved claw blade)
 * so the 3D canvas studio renders immediately even before external .stl files are loaded.
 */
export function buildProceduralKarambitMesh(subject = 'w282_p14_c01'): ParsedMesh3D {
  const isC10a = subject.toLowerCase().includes('c10a');
  const halfT = isC10a ? 2.25 : 2.85;
  const rawTris: [
    [number, number, number],
    [number, number, number],
    [number, number, number],
  ][] = [];

  // Ring annulus (inner radius 12.45 mm, outer radius 17.65 mm, 24 segments)
  const nRing = 24;
  const rIn = 12.45;
  const rOut = 17.65;
  for (let i = 0; i < nRing; i++) {
    const a0 = (i / nRing) * Math.PI * 2;
    const a1 = ((i + 1) / nRing) * Math.PI * 2;
    const i0: [number, number] = [rIn * Math.cos(a0), rIn * Math.sin(a0)];
    const i1: [number, number] = [rIn * Math.cos(a1), rIn * Math.sin(a1)];
    const o0: [number, number] = [rOut * Math.cos(a0), rOut * Math.sin(a0)];
    const o1: [number, number] = [rOut * Math.cos(a1), rOut * Math.sin(a1)];

    // Top (+halfT)
    rawTris.push([
      [i0[0], i0[1], halfT],
      [o0[0], o0[1], halfT],
      [o1[0], o1[1], halfT],
    ]);
    rawTris.push([
      [i0[0], i0[1], halfT],
      [o1[0], o1[1], halfT],
      [i1[0], i1[1], halfT],
    ]);
    // Bottom (-halfT)
    rawTris.push([
      [i0[0], i0[1], -halfT],
      [o1[0], o1[1], -halfT],
      [o0[0], o0[1], -halfT],
    ]);
    rawTris.push([
      [i0[0], i0[1], -halfT],
      [i1[0], i1[1], -halfT],
      [o1[0], o1[1], -halfT],
    ]);
    // Inner bore wall
    rawTris.push([
      [i0[0], i0[1], -halfT],
      [i0[0], i0[1], halfT],
      [i1[0], i1[1], halfT],
    ]);
    rawTris.push([
      [i0[0], i0[1], -halfT],
      [i1[0], i1[1], halfT],
      [i1[0], i1[1], -halfT],
    ]);
    // Outer ring wall
    rawTris.push([
      [o0[0], o0[1], -halfT],
      [o1[0], o1[1], halfT],
      [o0[0], o0[1], halfT],
    ]);
    rawTris.push([
      [o0[0], o0[1], -halfT],
      [o1[0], o1[1], -halfT],
      [o1[0], o1[1], halfT],
    ]);
  }

  // Curved grip + hawkbill claw blade strip from x = 16 mm to tip (187.86, -53.47)
  const nSpan = 36;
  const spinePts: [number, number, number][] = [];
  const edgePts: [number, number, number][] = [];
  for (let i = 0; i <= nSpan; i++) {
    const s = i / nSpan;
    const x = 16.0 + s * (187.86 - 16.0);
    // Curved claw centerline y(s) dropping to -53.47 mm at tip
    const yCenter =
      s < 0.45
        ? 4.0 * Math.sin((s / 0.45) * Math.PI)
        : -53.47 * Math.pow((s - 0.45) / 0.55, 1.65);
    const width = (1 - s) * 24.0 + s * 1.2;
    const localHalfT = halfT * (1.0 - 0.72 * Math.pow(s, 2.2));
    spinePts.push([x, yCenter + width * 0.52, localHalfT]);
    edgePts.push([x, yCenter - width * 0.48, localHalfT]);
  }

  for (let i = 0; i < nSpan; i++) {
    const sp0 = spinePts[i];
    const sp1 = spinePts[i + 1];
    const ed0 = edgePts[i];
    const ed1 = edgePts[i + 1];
    // Top face
    rawTris.push([
      [ed0[0], ed0[1], ed0[2]],
      [ed1[0], ed1[1], ed1[2]],
      [sp1[0], sp1[1], sp1[2]],
    ]);
    rawTris.push([
      [ed0[0], ed0[1], ed0[2]],
      [sp1[0], sp1[1], sp1[2]],
      [sp0[0], sp0[1], sp0[2]],
    ]);
    // Bottom face
    rawTris.push([
      [ed0[0], ed0[1], -ed0[2]],
      [sp1[0], sp1[1], -sp1[2]],
      [ed1[0], ed1[1], -ed1[2]],
    ]);
    rawTris.push([
      [ed0[0], ed0[1], -ed0[2]],
      [sp0[0], sp0[1], -sp0[2]],
      [sp1[0], sp1[1], -sp1[2]],
    ]);
    // Spine side wall
    rawTris.push([
      [sp0[0], sp0[1], -sp0[2]],
      [sp1[0], sp1[1], sp1[2]],
      [sp0[0], sp0[1], sp0[2]],
    ]);
    rawTris.push([
      [sp0[0], sp0[1], -sp0[2]],
      [sp1[0], sp1[1], -sp1[2]],
      [sp1[0], sp1[1], sp1[2]],
    ]);
    // Inside edge side wall
    rawTris.push([
      [ed0[0], ed0[1], -ed0[2]],
      [ed0[0], ed0[1], ed0[2]],
      [ed1[0], ed1[1], ed1[2]],
    ]);
    rawTris.push([
      [ed0[0], ed0[1], -ed0[2]],
      [ed1[0], ed1[1], ed1[2]],
      [ed1[0], ed1[1], -ed1[2]],
    ]);
  }
  // End caps at i = 0 and i = nSpan
  const s0 = spinePts[0];
  const e0 = edgePts[0];
  rawTris.push([
    [e0[0], e0[1], -e0[2]],
    [s0[0], s0[1], s0[2]],
    [e0[0], e0[1], e0[2]],
  ]);
  rawTris.push([
    [e0[0], e0[1], -e0[2]],
    [s0[0], s0[1], -s0[2]],
    [s0[0], s0[1], s0[2]],
  ]);
  const sn = spinePts[nSpan];
  const en = edgePts[nSpan];
  rawTris.push([
    [en[0], en[1], -en[2]],
    [en[0], en[1], en[2]],
    [sn[0], sn[1], sn[2]],
  ]);
  rawTris.push([
    [en[0], en[1], -en[2]],
    [sn[0], sn[1], sn[2]],
    [sn[0], sn[1], -sn[2]],
  ]);

  return buildParsedMeshFromRawTriangles(subject, rawTris);
}
