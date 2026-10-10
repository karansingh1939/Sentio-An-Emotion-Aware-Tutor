import { escapeHtml } from '../core/html.js';
// Documents View Controller for Sentio (ES Module)
import { sentioAPI } from '../core/api.js';
import { toast } from '../components/ui.js';
import { store } from '../core/store.js';

export class DocumentsView {
  constructor(containerId) {
    this.container = document.getElementById(containerId);
    this.documents = [];
    this.filterQuery = '';
    this.ocrReady = false;
  }

  async init() {
    // Listen to route changes to load documents when opened
    store.subscribe('activeRoute', (route) => {
      if (route === '#/documents') {
        this.loadDocuments();
      }
    });
  }

  async loadDocuments() {
    this.container.innerHTML = `
      <div style="display:flex;align-items:center;justify-content:center;height:60%;">
        <sentio-loader size="32px"></sentio-loader>
      </div>
    `;

    try {
      const [res, capabilities] = await Promise.all([
        sentioAPI.get('/documents'),
        sentioAPI.get('/documents/capabilities'),
      ]);
      this.ocrReady = capabilities.ocr_available;
      this.documents = res.documents || [];
      this.render();
      this.bindEvents();
    } catch (e) {
      this.container.innerHTML = `
        <div style="padding:40px;text-align:center;">
          <div style="font-size:24px;margin-bottom:12px;">⚠️</div>
          <div style="color:var(--red);font-weight:bold;">Failed to load Document Library</div>
          <div style="color:var(--text-dim);font-size:11px;margin-top:8px;">${escapeHtml(e.message)}</div>
          <button id="retry-docs-btn" style="margin-top:16px;background:var(--accent);color:var(--bg);border:none;padding:8px 16px;border-radius:var(--radius);cursor:pointer;font-family:var(--mono);">Retry</button>
        </div>
      `;
      const btn = this.container.querySelector('#retry-docs-btn');
      if (btn) btn.onclick = () => this.loadDocuments();
    }
  }

  render() {
    // Filter documents based on query
    const filteredDocs = this.documents.filter(
      (d) =>
        d.filename.toLowerCase().includes(this.filterQuery.toLowerCase()) ||
        d.category.toLowerCase().includes(this.filterQuery.toLowerCase()),
    );

    this.container.innerHTML = `
      <div class="view-header" style="margin-bottom:20px;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px;">
        <div>
          <h2 style="font-family:var(--display);font-weight:800;color:var(--text);margin-bottom:6px;">Document Library</h2>
          <p style="color:var(--text-dim);font-size:11px;">Upload textbooks, lecture slides, and notes for context-grounded AI tutoring.</p>
        </div>
        <button ${store.getState('currentUser')?.role === 'admin' ? '' : 'hidden'} id="sync-library-btn" style="background:none;color:var(--accent);border:1px solid var(--accent);padding:8px 16px;border-radius:var(--radius);cursor:pointer;font-family:var(--mono);font-size:11px;font-weight:bold;transition:background 0.2s;">
          🔄 Sync Disk Folder
        </button>
      </div>

      <div style="display:grid;grid-template-columns:1fr 340px;gap:20px;width:100%;">
        <!-- Left: Search and List -->
        <div style="display:flex;flex-direction:column;gap:16px;">
          <sentio-card title="Registered Study Materials">
            <div style="display:flex;gap:10px;margin-bottom:16px;">
              <input type="text" id="doc-search-input" value="${escapeHtml(this.filterQuery)}" placeholder="Search files by name or category..." style="flex:1;background:var(--bg3);border:1px solid var(--border);border-radius:var(--radius);padding:8px 12px;color:var(--text);font-family:var(--mono);font-size:11px;outline:none;" />
            </div>

            ${
              filteredDocs.length === 0
                ? `
              <sentio-empty-state message="No documents match your query or library is empty." icon="📂"></sentio-empty-state>
            `
                : `
              <div style="overflow-x:auto;">
                <table style="width:100%;border-collapse:collapse;font-size:11px;text-align:left;">
                  <thead>
                    <tr style="border-bottom:1px solid var(--border);color:var(--text-dim);">
                      <th style="padding:10px;">Filename</th>
                      <th style="padding:10px;">Category</th>
                      <th style="padding:10px;">Extraction</th><th style="padding:10px;">Chunks</th>
                      <th style="padding:10px;">Status</th>
                      <th style="padding:10px;text-align:right;">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    ${filteredDocs
                      .map((d) => {
                        const statusColor =
                          d.status === 'indexed'
                            ? 'var(--green)'
                            : d.status === 'failed'
                              ? 'var(--red)'
                              : 'var(--yellow)';
                        const statusIcon =
                          d.status === 'indexed' ? '✅' : d.status === 'failed' ? '❌' : '⏳';
                        return `
                        <tr style="border-bottom:1px solid var(--border);color:var(--text);">
                          <td style="padding:10px;max-width:240px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;" title="${escapeHtml(d.filename)}">
                            ${escapeHtml(d.filename)}
                          </td>
                          <td style="padding:10px;text-transform:capitalize;color:var(--text-dim);">${escapeHtml(d.category)}</td>
                          <td style="padding:10px;">${escapeHtml(d.extraction_method || 'text')}</td><td style="padding:10px;font-family:var(--mono);">${d.chunk_count || 0}</td>
                          <td style="padding:10px;">
                            <span style="color:${statusColor};font-weight:bold;font-size:10px;">
                              ${statusIcon} ${escapeHtml(d.status ? d.status.toUpperCase() : 'PENDING')}
                            </span>
                          </td>
                          <td style="padding:10px;text-align:right;">
                            <button class="delete-doc-btn" data-id="${escapeHtml(d.id)}" style="background:none;border:none;color:var(--red);cursor:pointer;font-family:var(--mono);font-size:11px;">Delete</button>
                          </td>
                        </tr>
                      `;
                      })
                      .join('')}
                  </tbody>
                </table>
              </div>
            `
            }
          </sentio-card>
        </div>

        <!-- Right: Upload Panel -->
        <div style="display:flex;flex-direction:column;gap:20px;">
          <sentio-card title="📤 Add Study Material">
            <div id="drop-zone" style="border:2px dashed var(--border);border-radius:var(--radius-lg);padding:24px 16px;text-align:center;background:var(--bg3);cursor:pointer;transition:border-color 0.2s, background 0.2s;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:8px;">
              <span style="font-size:32px;">📄</span>
              <span style="font-size:11px;font-weight:bold;color:var(--text);">Drag & Drop your file here</span>
              <span style="font-size:10px;color:var(--text-dim);">or click to browse filesystem</span>
              <input type="file" id="file-uploader" style="display:none;" accept="${this.ocrReady ? '.pdf,.docx,.txt,.png,.jpg,.jpeg' : '.pdf,.docx,.txt'}" />
            </div>

            <p style="font-size:11px;color:var(--text-dim);">20 MiB maximum. ${this.ocrReady ? 'English OCR enabled; up to 20 scanned pages.' : 'Scans and images require the optional OCR tools.'}</p><div style="margin-top:16px;">
              <label style="display:block;font-size:10px;color:var(--text-dim);margin-bottom:6px;font-weight:bold;">Subject Category</label>
              <select id="upload-category" style="width:100%;background:var(--bg3);border:1px solid var(--border);border-radius:var(--radius);padding:8px;color:var(--text);font-family:var(--mono);font-size:11px;outline:none;">
                <option value="uploaded">General Uploads</option>
                <option value="textbooks">Textbooks</option>
                <option value="notes">Lecture Notes</option>
                <option value="assignments">Assignments</option>
                <option value="reference">Reference Materials</option>
              </select>
            </div>

            <div id="upload-progress-bar" style="display:none;margin-top:16px;background:var(--border);height:6px;border-radius:3px;overflow:hidden;position:relative;">
              <div id="upload-progress-fill" style="width:0%;background:var(--accent);height:100%;transition:width 0.2s;"></div>
            </div>
            <div id="upload-progress-text" style="display:none;font-size:10px;color:var(--accent);text-align:center;margin-top:6px;font-weight:bold;">Uploading...</div>
          </sentio-card>
        </div>
      </div>
    `;
  }

  bindEvents() {
    // 1. Search filter binding
    const search = this.container.querySelector('#doc-search-input');
    if (search) {
      search.oninput = (e) => {
        this.filterQuery = e.target.value;
        this.render();
        this.bindEvents(); // Rebind since HTML changed
      };
    }

    // 2. Sync Library Button binding
    const syncBtn = this.container.querySelector('#sync-library-btn');
    if (syncBtn) {
      syncBtn.onclick = async () => {
        store.setState('loading', true);
        try {
          const res = await sentioAPI.post('/documents/sync');
          toast(`Library scan finished! Synced: ${res.report?.indexed_count || 0} files.`);
          this.loadDocuments();
        } catch (e) {
          toast('Sync failed: ' + e.message, true);
        } finally {
          store.setState('loading', false);
        }
      };
    }

    // 3. Delete Document buttons binding
    this.container.querySelectorAll('.delete-doc-btn').forEach((btn) => {
      btn.onclick = async (e) => {
        const docId = e.target.dataset.id;
        if (
          !confirm(
            'Are you sure you want to delete this document? This will remove all Qdrant vector chunks and delete the raw file from disk.',
          )
        ) {
          return;
        }

        store.setState('loading', true);
        try {
          await sentioAPI.delete(`/documents/${docId}`);
          toast('Document deleted successfully.');
          this.loadDocuments();
        } catch (err) {
          toast('Delete failed: ' + err.message, true);
        } finally {
          store.setState('loading', false);
        }
      };
    });

    // 4. Drag and Drop + File Uploader Binding
    const dropZone = this.container.querySelector('#drop-zone');
    const uploader = this.container.querySelector('#file-uploader');
    const categorySelect = this.container.querySelector('#upload-category');

    if (dropZone && uploader) {
      dropZone.onclick = () => uploader.click();

      // Drag events
      dropZone.ondragover = (e) => {
        e.preventDefault();
        dropZone.style.borderColor = 'var(--accent)';
        dropZone.style.background = 'rgba(0, 200, 255, 0.05)';
      };

      dropZone.ondragleave = () => {
        dropZone.style.borderColor = 'var(--border)';
        dropZone.style.background = 'var(--bg3)';
      };

      dropZone.ondrop = (e) => {
        e.preventDefault();
        dropZone.style.borderColor = 'var(--border)';
        dropZone.style.background = 'var(--bg3)';
        const files = e.dataTransfer.files;
        if (files.length > 0) {
          this.uploadFile(files[0], categorySelect.value);
        }
      };

      uploader.onchange = (e) => {
        const files = e.target.files;
        if (files.length > 0) {
          this.uploadFile(files[0], categorySelect.value);
        }
      };
    }
  }

  async uploadFile(file, category) {
    const fill = this.container.querySelector('#upload-progress-fill');
    const progressText = this.container.querySelector('#upload-progress-text');
    const progressBar = this.container.querySelector('#upload-progress-bar');

    if (progressBar && fill && progressText) {
      progressBar.style.display = 'block';
      progressText.style.display = 'block';
      fill.style.width = '10%';
      progressText.textContent = 'Uploading file content...';
    }

    const formData = new FormData();
    formData.append('file', file);
    formData.append('category', category);

    try {
      if (fill) fill.style.width = '40%';
      if (progressText)
        progressText.textContent = 'Extracting text and indexing; scanned pages may take longer...';
      await sentioAPI.request('/documents/upload', {
        method: 'POST',
        body: formData,
        timeout: 2500000,
      });

      if (fill && progressText) {
        fill.style.width = '100%';
        progressText.textContent = 'Indexing complete! Grounding active.';
      }
      toast('Document uploaded and indexed successfully!');
      setTimeout(() => this.loadDocuments(), 1200);
    } catch (e) {
      if (fill && progressText) {
        fill.style.width = '0%';
        progressText.textContent = 'Upload failed!';
        progressText.style.color = 'var(--red)';
      }
      toast('Upload failed: ' + e.message, true);
    }
  }
}
