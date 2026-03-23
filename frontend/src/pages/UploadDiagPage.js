import React, { useState, useRef, useCallback } from 'react';
import { compressImage } from '../utils/imageCompress';
import { taskService } from '../services/api';

const UploadDiagPage = () => {
  const [log, setLog] = useState([]);
  const [taskId, setTaskId] = useState('');
  const [running, setRunning] = useState(false);
  const fileRef = useRef();
  const annotFileRef = useRef();

  const addLog = useCallback((msg, type = 'info') => {
    const ts = new Date().toLocaleTimeString();
    setLog(prev => [...prev, { ts, msg, type }]);
  }, []);

  const clearLog = () => setLog([]);

  const fetchTaskId = async () => {
    try {
      const token = localStorage.getItem('token');
      if (!token) { addLog('NOT LOGGED IN — log in first', 'error'); return null; }
      const resp = await fetch('/api/tasks?limit=1', { headers: { Authorization: `Bearer ${token}` } });
      const data = await resp.json();
      const id = data?.items?.[0]?.id;
      if (!id) { addLog('No tasks found', 'error'); return null; }
      setTaskId(id);
      addLog(`Using task: ${id.slice(0,8)}...`);
      return id;
    } catch (e) {
      addLog(`Failed to get task: ${e.message}`, 'error');
      return null;
    }
  };

  const runTest1 = async () => {
    setRunning(true);
    clearLog();
    addLog('=== TEST 1: Upload without annotation (5 runs) ===');
    const tid = taskId || await fetchTaskId();
    if (!tid) { setRunning(false); return; }

    let passed = 0;
    for (let i = 1; i <= 5; i++) {
      addLog(`--- Run ${i}/5 ---`);
      try {
        const input = fileRef.current;
        if (!input?.files?.[0]) {
          addLog('Select a photo first', 'error');
          setRunning(false);
          return;
        }
        const raw = input.files[0];
        addLog(`Raw file: ${raw.name} ${raw.size} bytes ${raw.type}`);

        const compressed = await compressImage(raw);
        addLog(`Compressed: ${compressed.name} ${compressed.size} bytes ${compressed.type}`);

        const t0 = Date.now();
        await taskService.uploadAttachment(tid, compressed);
        const elapsed = Date.now() - t0;
        addLog(`Upload OK (${elapsed}ms)`, 'success');
        passed++;
      } catch (e) {
        const status = e?.response?.status;
        const detail = e?.response?.data?.detail;
        const code = e?.code;
        addLog(`FAILED: status=${status} code=${code} detail=${JSON.stringify(detail)} msg=${e.message}`, 'error');
      }
      if (i < 5) await new Promise(r => setTimeout(r, 1000));
    }
    addLog(`=== TEST 1 RESULT: ${passed}/5 passed ===`, passed === 5 ? 'success' : 'error');
    setRunning(false);
  };

  const runTest2 = async () => {
    setRunning(true);
    clearLog();
    addLog('=== TEST 2: Annotation export only (5 runs) ===');

    let passed = 0;
    for (let i = 1; i <= 5; i++) {
      addLog(`--- Run ${i}/5 ---`);
      try {
        const input = fileRef.current;
        if (!input?.files?.[0]) {
          addLog('Select a photo first', 'error');
          setRunning(false);
          return;
        }
        const raw = input.files[0];
        const compressed = await compressImage(raw);

        const img = new Image();
        const url = URL.createObjectURL(compressed);
        await new Promise((resolve, reject) => {
          img.onload = resolve;
          img.onerror = reject;
          img.src = url;
        });

        const canvas = document.createElement('canvas');
        canvas.width = img.naturalWidth;
        canvas.height = img.naturalHeight;
        const ctx = canvas.getContext('2d');
        ctx.drawImage(img, 0, 0);
        ctx.strokeStyle = 'red';
        ctx.lineWidth = 4;
        ctx.beginPath();
        ctx.moveTo(50, 50);
        ctx.lineTo(canvas.width - 50, canvas.height - 50);
        ctx.stroke();
        URL.revokeObjectURL(url);

        addLog(`Canvas: ${canvas.width}x${canvas.height}`);

        const blob = await new Promise(resolve =>
          canvas.toBlob(resolve, 'image/jpeg', 0.70)
        );

        if (!blob || blob.size === 0) {
          addLog(`FAILED: blob is ${blob ? 'empty' : 'null'}`, 'error');
        } else {
          addLog(`Blob OK: ${blob.size} bytes (${(blob.size/1024).toFixed(0)} KB) type=${blob.type}`, 'success');
          passed++;
        }
      } catch (e) {
        addLog(`FAILED: ${e.message}`, 'error');
      }
      if (i < 5) await new Promise(r => setTimeout(r, 500));
    }
    addLog(`=== TEST 2 RESULT: ${passed}/5 passed ===`, passed === 5 ? 'success' : 'error');
    setRunning(false);
  };

  const runTest3 = async () => {
    setRunning(true);
    clearLog();
    addLog('=== TEST 3: Annotation + Upload (5 runs) ===');
    const tid = taskId || await fetchTaskId();
    if (!tid) { setRunning(false); return; }

    let passed = 0;
    for (let i = 1; i <= 5; i++) {
      addLog(`--- Run ${i}/5 ---`);
      try {
        const input = fileRef.current;
        if (!input?.files?.[0]) {
          addLog('Select a photo first', 'error');
          setRunning(false);
          return;
        }
        const raw = input.files[0];
        const compressed = await compressImage(raw);
        addLog(`Compressed: ${compressed.size} bytes`);

        const img = new Image();
        const url = URL.createObjectURL(compressed);
        await new Promise((resolve, reject) => {
          img.onload = resolve;
          img.onerror = reject;
          img.src = url;
        });

        const canvas = document.createElement('canvas');
        canvas.width = img.naturalWidth;
        canvas.height = img.naturalHeight;
        const ctx = canvas.getContext('2d');
        ctx.drawImage(img, 0, 0);
        ctx.strokeStyle = 'red';
        ctx.lineWidth = 4;
        ctx.beginPath();
        ctx.moveTo(50, 50);
        ctx.lineTo(canvas.width - 50, canvas.height - 50);
        ctx.stroke();
        URL.revokeObjectURL(url);

        const blob = await new Promise(resolve =>
          canvas.toBlob(resolve, 'image/jpeg', 0.70)
        );
        if (!blob || blob.size === 0) {
          addLog('Blob export failed', 'error');
          continue;
        }
        addLog(`Blob: ${blob.size} bytes (${(blob.size/1024).toFixed(0)} KB)`);
        const annotatedFile = new File([blob], 'annotated.jpg', { type: 'image/jpeg' });

        const t0 = Date.now();
        await taskService.uploadAttachment(tid, compressed);
        addLog(`Original uploaded (${Date.now()-t0}ms)`);

        await new Promise(r => setTimeout(r, 500));

        const t1 = Date.now();
        await taskService.uploadAttachment(tid, annotatedFile);
        addLog(`Annotated uploaded (${Date.now()-t1}ms)`, 'success');
        passed++;
      } catch (e) {
        const status = e?.response?.status;
        const detail = e?.response?.data?.detail;
        const code = e?.code;
        addLog(`FAILED: status=${status} code=${code} detail=${JSON.stringify(detail)} msg=${e.message}`, 'error');
      }
      if (i < 5) await new Promise(r => setTimeout(r, 1500));
    }
    addLog(`=== TEST 3 RESULT: ${passed}/5 passed ===`, passed === 5 ? 'success' : 'error');
    setRunning(false);
  };

  const colorMap = { success: '#22c55e', error: '#ef4444', info: '#94a3b8' };

  return (
    <div style={{ padding: 16, maxWidth: 600, margin: '0 auto', fontFamily: 'monospace', fontSize: 13 }}>
      <h2 style={{ marginBottom: 12 }}>Upload Diagnostics</h2>

      <div style={{ marginBottom: 16 }}>
        <label style={{ display: 'block', marginBottom: 6, fontWeight: 'bold' }}>
          Select a photo (camera or gallery):
        </label>
        <input ref={fileRef} type="file" accept="image/*" style={{ marginBottom: 8 }} />
      </div>

      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 16 }}>
        <button onClick={runTest1} disabled={running}
          style={{ padding: '10px 16px', background: '#3b82f6', color: '#fff', border: 'none', borderRadius: 6, opacity: running ? 0.5 : 1 }}>
          Test 1: Upload Only
        </button>
        <button onClick={runTest2} disabled={running}
          style={{ padding: '10px 16px', background: '#8b5cf6', color: '#fff', border: 'none', borderRadius: 6, opacity: running ? 0.5 : 1 }}>
          Test 2: Export Only
        </button>
        <button onClick={runTest3} disabled={running}
          style={{ padding: '10px 16px', background: '#f59e0b', color: '#fff', border: 'none', borderRadius: 6, opacity: running ? 0.5 : 1 }}>
          Test 3: Annot+Upload
        </button>
        <button onClick={clearLog}
          style={{ padding: '10px 16px', background: '#6b7280', color: '#fff', border: 'none', borderRadius: 6 }}>
          Clear
        </button>
      </div>

      <div style={{ background: '#1e1e1e', color: '#e0e0e0', padding: 12, borderRadius: 8, minHeight: 200, maxHeight: '60vh', overflowY: 'auto', whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>
        {log.length === 0 && <span style={{ color: '#666' }}>Select a photo, then run a test...</span>}
        {log.map((entry, i) => (
          <div key={i} style={{ color: colorMap[entry.type] || '#e0e0e0', marginBottom: 2 }}>
            <span style={{ color: '#666' }}>{entry.ts}</span> {entry.msg}
          </div>
        ))}
      </div>
    </div>
  );
};

export default UploadDiagPage;
