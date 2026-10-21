/* Same-origin frame sizing for the read-only measured-scan explorer. */
window.addEventListener('message', function(event) {
  if (event.origin !== window.location.origin) return;
  if (!event.data || !['wifi-integrity-explorer','wifi-indicator-atlas','wifi-scan-compare','wifi-evidence-matrix'].includes(event.data.source)) return;
  const requested = Number(event.data.height);
  if (!Number.isFinite(requested) || requested < 500 || requested > 10000) return;
  document.querySelectorAll('iframe[src*="assets/interactive/index.html"], iframe[src*="assets/interactive/comparison.html"], iframe[src*="assets/interactive/evidence.html"], iframe[src*="assets/indicator-atlas/index.html"]').forEach(function(frame) {
    if (frame.contentWindow === event.source) {
      const height = Math.round(requested + 16);
      if (Math.abs(frame.getBoundingClientRect().height - height) > 12) frame.style.height = height + 'px';
    }
  });
});
