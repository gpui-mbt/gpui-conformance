import test from 'node:test';
import assert from 'node:assert/strict';
import {expectedBinaryPolygonBounds,assertCandidatePolygonCoverage,verifyCandidateSourceBehavior} from './gradient-candidate-behavior.mjs';
import {rasterSourcePolygon} from './gradient-candidate-polygon-fixture.mjs';
test('authored pixel-center formula agrees with independent convex-edge rasterization beyond paired sizes',()=>{
 for(const [w,h] of [[240,300],[249,401],[337,515],[600,960],[601,601],[960,600],[1024,1024],[1536,800],[2048,2048]]){
  const {bounds}=rasterSourcePolygon(w,h);assert.deepEqual(expectedBinaryPolygonBounds(w,h),bounds);assert.doesNotThrow(()=>assertCandidatePolygonCoverage(bounds,w,h));
 }
});
test('rerasterized omitted-origin and authored-width mistakes reject, separately from compiled faults',()=>{
 for(const [w,h] of [[249,401],[600,960],[960,600],[1536,800]])for(const fault of [{originX:16},{widthDelta:8},{widthDelta:-8}]){
  const {bounds}=rasterSourcePolygon(w,h,fault);assert.throws(()=>assertCandidatePolygonCoverage(bounds,w,h),/Candidate source polygon pixel-center binary coverage/);
 }
});
test('candidate behavior requires both stable sample sets',()=>{assert.throws(()=>verifyCandidateSourceBehavior({runtime:'moonbit'},{images:{}}),/Both independent/);});
