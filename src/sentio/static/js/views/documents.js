import { escapeHtml } from '../core/html.js';
// Documents View Controller for Sentio (ES Module)
import { sentioAPI } from '../core/api.js';
import { toast } from '../components/ui.js';
import { store } from '../core/store.js';
import { pendingJobKey, runPracticeJob } from '../core/jobs.js';

export class DocumentsView {
  constructor(containerId) {
    this.container = document.getElementById(containerId);
    this.documents = [];
    this.filterQuery = '';
    this.ocrReady = false;
    this.revision = 0;
    this.uploadInProgress = false;
    this.justUploadedId = null;
  }

  async init() {
    store.subscribe('currentUser', () => {
      this.justUploadedId = null;
      this.documents = [];
      this.revision++;
    });
    // Listen to route changes to load documents when opened
    store.subscribe('activeRoute', (route) => {
      if (route === '#/documents') {
        this.loadDocuments();
      } else {
        this.revision++;
      }
    });
  }

  async loadDocuments() {
    const revision = ++this.revision;
    const owner = store.getState('currentUser')?.id;
    const current = () =>
      this.revision === revision &&
      store.getState('currentUser')?.id === owner &&
      store.getState('activeRoute') === '#/documents';
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
      if (!current()) return;
      this.ocrReady = capabilities.ocr_available;
      this.documents = res.documents || [];
      this.render();
      this.bindEvents();
      if (localStorage.getItem(pendingJobKey('/documents/jobs', false))) this.uploadFile(null);
    } catch (e) {
      if (!current()) return;
      this.container.innerHTML = `
        <div style="padding:40px;text-align:center;">
          <div style="font-size:24px;margin-bottom:12px;">⚠️</div>
          <div style="color:var(--red);font-weight:bold;">Failed to load Document Library</div>
          <div style="color:var(--text-dim);font-size:14px;margin-top:8px;">${escapeHtml(e.message)}</div>
          <button id="retry-docs-btn" style="margin-top:16px;background:var(--accent);color:var(--bg);border:none;padding:8px 16px;border-radius:var(--radius);cursor:pointer;font-family:var(--mono);">Retry</button>
        </div>
      `;
      const btn = this.container.querySelector('#retry-docs-btn');
      if (btn) btn.onclick = () => this.loadDocuments();
    }
  }

  render() {
    // Filter documents based on query
    const filteredDocs = this.documents;

    this.container.innerHTML = `
      <div class="view-header" style="margin-bottom:20px;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px;">
        <div>
          <h2 style="font-family:var(--display);font-weight:800;color:var(--text);margin-bottom:6px;">Document Library</h2>
          <p style="color:var(--text-dim);font-size:14px;">Upload your notes, then choose Study to ask questions about them.</p>
        </div>
        <button ${store.getState('currentUser')?.role === 'admin' ? '' : 'hidden'} id="sync-library-btn" style="background:none;color:var(--accent);border:1px solid var(--accent);padding:8px 16px;border-radius:var(--radius);cursor:pointer;font-family:var(--mono);font-size:14px;font-weight:bold;transition:background 0.2s;">
          🔄 Sync Disk Folder
        </button>
      </div>

      ${this.justUploadedId ? `<div class="notice library-ready" role="status">Your notes are ready. <button class="workspace-action primary study-doc-btn" data-id="${escapeHtml(this.justUploadedId)}">Study these notes</button></div>` : ''}
      <div class="library-layout" style="display:grid;grid-template-columns:1fr 340px;gap:20px;width:100%;">
        <!-- Left: Search and List -->
        <div style="display:flex;flex-direction:column;gap:16px;">
          <sentio-card title="Your notes">
            <div style="display:flex;gap:10px;margin-bottom:16px;">
              <input type="text" id="doc-search-input" value="${escapeHtml(this.filterQuery)}" placeholder="Search files by name or category..." style="flex:1;background:var(--bg3);border:1px solid var(--border);border-radius:var(--radius);padding:8px 12px;color:var(--text);font-family:var(--mono);font-size:14px;outline:none;" />
            </div>

            ${
              filteredDocs.length === 0
                ? `
              <sentio-empty-state message="Your library is empty. Add a PDF, Word document or text file to begin." icon="📂"></sentio-empty-state>
            `
                : `
              <div style="overflow-x:auto;">
                <p id="doc-search-status" role="status"></p>
                <table class="library-table" style="width:100%;border-collapse:collapse;font-size:14px;text-align:left;">
                  <thead>
                    <tr style="border-bottom:1px solid var(--border);color:var(--text-dim);">
                      <th style="padding:10px;">Filename</th>
                      <th style="padding:10px;">Category</th>
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
                        <tr class="document-row" data-search="${escapeHtml((d.filename + ' ' + d.category).toLowerCase())}" style="border-bottom:1px solid var(--border);color:var(--text);">
                          <td style="padding:10px;max-width:240px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;" title="${escapeHtml(d.filename)}">
                            ${escapeHtml(d.filename)}
                          </td>
                          <td style="padding:10px;text-transform:capitalize;color:var(--text-dim);">${escapeHtml(d.category)}</td>
                          <td style="padding:10px;">
                            <span style="color:${statusColor};font-weight:bold;font-size:14px;">
                              ${statusIcon} ${escapeHtml(d.status === 'indexed' ? 'Ready to study' : d.status === 'failed' ? 'Needs retry' : 'Processing')}
                            </span>
                          </td>
                          <td style="padding:10px;text-align:right;">
                            <button class="workspace-action primary study-doc-btn" data-id="${escapeHtml(d.id)}" ${d.status === 'indexed' ? '' : 'disabled'}>Study</button>
                            <button class="preview-doc-btn" data-id="${escapeHtml(d.id)}">Preview</button>
                            <button class="delete-doc-btn" data-id="${escapeHtml(d.id)}" style="background:none;border:none;color:var(--red);cursor:pointer;font-family:var(--mono);font-size:14px;">Delete</button>
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
          <sentio-card title="1. Add your notes">
            <div id="drop-zone" role="button" tabindex="0" aria-label="Choose a study material file" style="border:2px dashed var(--border);border-radius:var(--radius-lg);padding:24px 16px;text-align:center;background:var(--bg3);cursor:pointer;transition:border-color 0.2s, background 0.2s;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:8px;">
              <span style="font-size:32px;">📄</span>
              <span style="font-size:14px;font-weight:bold;color:var(--text);">Drag & Drop your file here</span>
              <span style="font-size:14px;color:var(--text-dim);">or choose a file</span>
              <input type="file" id="file-uploader" style="display:none;" accept="${this.ocrReady ? '.pdf,.docx,.txt,.png,.jpg,.jpeg' : '.pdf,.docx,.txt'}" />
            </div>

            <p style="font-size:14px;color:var(--text-dim);">20 MiB maximum. ${this.ocrReady ? 'English OCR enabled; up to 20 scanned pages.' : 'Scans and images require the optional OCR tools.'}</p><div style="margin-top:16px;">
              <label for="upload-category" style="display:block;font-size:14px;color:var(--text-dim);margin-bottom:6px;font-weight:bold;">Organize as</label>
<select id="upload-category" style="width:100%;background:var(--bg3);border:1px solid var(--border);border-radius:var(--radius);padding:8px;color:var(--text);font-family:var(--mono);font-size:14px;outline:none;">
                <option value="uploaded">General Uploads</option>
                <option value="textbooks">Textbooks</option>
                <option value="notes">Lecture Notes</option>
                <option value="assignments">Assignments</option>
                <option value="reference">Reference Materials</option>
              </select>
            </div>

            <div id="library-job" role="region" aria-label="Upload progress"></div>

          </sentio-card>
        </div>
      </div>
    `;
  }

  bindEvents() {
    this.container.querySelectorAll('.study-doc-btn').forEach((button) => {
      button.onclick = () =>
        window.tutorView?.createNewSessionDialog({
          documentId: button.dataset.id,
          document: this.documents.find((item) => item.id === button.dataset.id),
        });
    });
    // 1. Search filter binding
    const search = this.container.querySelector('#doc-search-input');
    if (search) {
      search.oninput = (e) => {
        this.filterQuery = e.target.value;
        this.applyFilter();
      };
    }

    this.applyFilter();
    this.container.querySelectorAll('.preview-doc-btn').forEach((button) => {
      button.onclick = () => this.previewDocument(button.dataset.id);
    });

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
    if (uploader) uploader.disabled = this.uploadInProgress;

    if (dropZone && uploader) {
      dropZone.onclick = () => {
        if (!this.uploadInProgress) uploader.click();
      };
      dropZone.onkeydown = (event) => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          dropZone.click();
        }
      };

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

  applyFilter() {
    let shown = 0;
    this.container.querySelectorAll('.document-row').forEach((row) => {
      row.hidden = !row.dataset.search.includes(this.filterQuery.toLowerCase());
      if (!row.hidden) shown++;
    });
    const status = this.container.querySelector('#doc-search-status');
    if (status) status.textContent = `${shown} matching material${shown === 1 ? '' : 's'}`;
  }

  async previewDocument(documentId) {
    const owner = store.getState('currentUser')?.id;
    const revision = this.revision;
    try {
      const result = await sentioAPI.get(`/documents/${documentId}/preview`);
      if (owner !== store.getState('currentUser')?.id || revision !== this.revision) return;
      const modal = document.createElement('sentio-modal');
      modal.setAttribute('title', result.document.filename);
      modal.innerHTML =
        '<p>Extracted source text. Check scans for recognition errors.</p><div class="document-preview"></div><button class="preview-more" type="button">Show more</button>';
      document.body.appendChild(modal);
      const append = (data) => {
        for (const chunk of data.chunks) {
          const section = document.createElement('section');
          section.innerHTML = `<h3>Page ${escapeHtml(chunk.page_number || 1)}</h3><p style="white-space:pre-wrap">${escapeHtml(chunk.text_content)}</p>`;
          modal.querySelector('.document-preview').appendChild(section);
        }
        const more = modal.querySelector('.preview-more');
        more.hidden = data.next_offset === null;
        more.onclick = async () => {
          more.disabled = true;
          try {
            append(
              await sentioAPI.get(`/documents/${documentId}/preview?offset=${data.next_offset}`),
            );
          } catch (error) {
            toast(error.message, true);
          } finally {
            more.disabled = false;
          }
        };
      };
      append(result);
    } catch (error) {
      toast('Preview unavailable: ' + error.message, true);
    }
  }

  async uploadFile(file, category) {
    if (this.uploadInProgress) {
      if (file) {
        this.queuedUpload = { file, category, owner: store.getState('currentUser')?.id };
        toast('This file will upload after the current library task finishes.');
      }
      return;
    }
    this.uploadInProgress = true;
    const owner = store.getState('currentUser')?.id;
    const revision = this.revision;
    const uploader = this.container.querySelector('#file-uploader');
    let refreshed = false;
    if (uploader) uploader.disabled = true;
    try {
      // A newly chosen file is a new intent. Finish reconnecting the previous
      // receipt before sending it, rather than consuming this file as a retry.
      const pendingKey = pendingJobKey('/documents/jobs', false);
      if (file && localStorage.getItem(pendingKey)) {
        try {
          await runPracticeJob(
            '/documents/jobs',
            null,
            this.container.querySelector('#library-job'),
            { sessionScoped: false },
          );
        } catch (error) {
          if (localStorage.getItem(pendingKey)) throw error;
        }
        if (owner !== store.getState('currentUser')?.id || localStorage.getItem(pendingKey)) return;
      }
      // Navigation can replace the progress panel while the prior receipt is read.
      if (!this.container.querySelector('#library-job')) await this.loadDocuments();
      if (
        owner !== store.getState('currentUser')?.id ||
        !this.container.querySelector('#library-job')
      )
        return;
      const form = new FormData();
      if (file) {
        form.append('file', file);
        form.append('category', category);
        const subject = store.getState('activeSession')?.subject;
        if (subject) form.append('subject', subject);
      }
      const result = await runPracticeJob(
        '/documents/jobs',
        null,
        this.container.querySelector('#library-job'),
        {
          sessionScoped: false,
          submit: (requestId) => {
            if (!file) throw new Error('Choose the file again to retry this upload.');
            return sentioAPI.request('/documents/jobs', {
              method: 'POST',
              body: form,
              headers: { 'Idempotency-Key': requestId },
            });
          },
        },
      );
      if (
        result &&
        owner === store.getState('currentUser')?.id &&
        store.getState('activeRoute') === '#/documents'
      ) {
        toast(
          'Study material saved. ' +
            (result.indexing_mode === 'keyword'
              ? 'Keyword search is available; semantic indexing was unavailable.'
              : 'Ready for study.'),
        );
        this.justUploadedId = result.document_id;
        this.loadDocuments();
        refreshed = true;
      }
    } catch (error) {
      if (owner === store.getState('currentUser')?.id && revision === this.revision) {
        this.container.querySelector('#library-job').textContent =
          error.message + ' Choose the file again to retry.';
        toast('Upload did not finish: ' + error.message, true);
      }
    } finally {
      this.uploadInProgress = false;
      if (uploader) uploader.disabled = false;
      const currentUploader = this.container.querySelector('#file-uploader');
      if (currentUploader && owner === store.getState('currentUser')?.id)
        currentUploader.disabled = false;
      if (
        !refreshed &&
        revision !== this.revision &&
        store.getState('activeRoute') === '#/documents' &&
        owner === store.getState('currentUser')?.id
      )
        this.loadDocuments();
      const next = this.queuedUpload;
      this.queuedUpload = null;
      if (
        next &&
        next.owner === store.getState('currentUser')?.id &&
        store.getState('activeRoute') === '#/documents'
      ) {
        await this.loadDocuments();
        if (
          next.owner === store.getState('currentUser')?.id &&
          store.getState('activeRoute') === '#/documents'
        )
          this.uploadFile(next.file, next.category);
      }
    }
  }
}
