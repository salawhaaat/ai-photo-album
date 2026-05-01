// ── CONFIGURE THESE after you deploy API Gateway ──────────────────────────────
const API_BASE = 'https://faftrzbgk7.execute-api.us-east-1.amazonaws.com/prod';
const API_KEY  = '9vidCvMUbf1PDdHZQWoTC3W9T1eBlFGb5FeWQlmJ';
// ──────────────────────────────────────────────────────────────────────────────

function doSearch() {
  const q = $('#searchInput').val().trim();
  if (!q) return;

  $('#resultsCard').show();
  $('#results').html('<p class="text-muted">Searching…</p>');

  $.ajax({
    url: `${API_BASE}/search`,
    method: 'GET',
    data: { q },
    headers: { 'x-api-key': API_KEY },
    success(data) {
      if (!data.results || data.results.length === 0) {
        $('#results').html('<p>No photos found for that query.</p>');
        return;
      }
      const html = data.results.map(r => `
        <div class="photo-card">
          <img src="${r.url}" alt="photo" onerror="this.src='https://via.placeholder.com/200?text=No+Image'">
          <div class="mt-1">
            ${r.labels.map(l => `<span class="badge bg-secondary">${l}</span>`).join('')}
          </div>
        </div>
      `).join('');
      $('#results').html(html);
    },
    error(err) {
      $('#results').html(`<p class="text-danger">Error: ${JSON.stringify(err.responseJSON || err.statusText)}</p>`);
    },
  });
}

function doUpload() {
  const file = $('#fileInput')[0].files[0];
  if (!file) { alert('Please select an image file first.'); return; }

  const customLabels = $('#customLabels').val().trim();
  const filename     = encodeURIComponent(file.name);

  $('#uploadStatus').html('<span class="text-info">Uploading…</span>');

  const headers = {
    'x-api-key':    API_KEY,
    'Content-Type': file.type || 'image/jpeg',
  };
  if (customLabels) {
    // Sent as x-amz-meta-customlabels → S3 stores as metadata
    headers['x-amz-meta-customLabels'] = customLabels;
  }

  $.ajax({
    url: `${API_BASE}/photos/${filename}`,
    method: 'PUT',
    data: file,
    processData: false,
    contentType: false,
    headers,
    success() {
      $('#uploadStatus').html(
        '<span class="text-success">Uploaded successfully! ' +
        'Wait ~5 seconds then search for your labels.</span>'
      );
      $('#fileInput').val('');
      $('#customLabels').val('');
    },
    error(err) {
      $('#uploadStatus').html(
        `<span class="text-danger">Upload failed: ${JSON.stringify(err.responseJSON || err.statusText)}</span>`
      );
    },
  });
}

$(document).ready(() => {
  // Press Enter to search
  $('#searchInput').on('keypress', e => { if (e.which === 13) doSearch(); });
});
