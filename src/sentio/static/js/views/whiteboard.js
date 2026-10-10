// Whiteboard View Controller for Sentio (ES Module)
import { sentioAPI } from '../core/api.js';
import { store } from '../core/store.js';
import { toast } from '../components/ui.js';

export class WhiteboardView {
  constructor(containerId) {
    this.container = document.getElementById(containerId);
    this.whiteboardId = 'wb_default_01';
    this.title = 'Recursion Flow';
    this.studentId = 'stu_001';

    this.shapes = [];
    this.undoStack = [];
    this.redoStack = [];

    this.currentTool = 'pen'; // pen | highlighter | eraser | line | arrow | rectangle | circle | text
    this.currentColor = '#00c8ff';
    this.currentWidth = 4;
    this.zoomLevel = 1.0;
    this.panX = 0;
    this.panY = 0;

    this.isDrawing = false;
    this.startX = 0;
    this.startY = 0;
    this.currentPoints = [];
    this.hasUnsavedChanges = false;
    this.autosaveInterval = null;
  }

  init() {
    store.subscribe('activeRoute', (route) => {
      if (route === '#/whiteboard') {
        this.studentId = store.getState('currentUser')?.id || 'stu_001';
        this.whiteboardId = 'wb_session_' + (store.getState('activeSessionId') || 'general');
        this.loadSessionState();
        this.startAutosave();
      } else {
        this.stopAutosave();
      }
    });
  }

  startAutosave() {
    this.stopAutosave();
    this.autosaveInterval = setInterval(() => {
      if (this.hasUnsavedChanges) {
        this.saveWhiteboard(true);
      }
    }, 15000);
  }

  stopAutosave() {
    if (this.autosaveInterval) {
      clearInterval(this.autosaveInterval);
      this.autosaveInterval = null;
    }
  }

  async loadSessionState() {
    this.container.innerHTML = `
      <div style="display:flex;align-items:center;justify-content:center;height:60%;">
        <sentio-loader size="32px"></sentio-loader>
      </div>
    `;

    try {
      const res = await sentioAPI.get(`/whiteboards/${this.whiteboardId}`);
      this.shapes = res.canvas_state?.shapes || [];
      this.title = res.title || 'Tutoring Space';
    } catch (e) {
      // Create new session locally if 404
      this.shapes = [];
      this.title = 'Whiteboard Diagram';
    }

    this.undoStack = [];
    this.redoStack = [];
    this.hasUnsavedChanges = false;
    this.render();
    this.initCanvas();
  }

  render() {
    this.container.innerHTML = `
      <div class="view-header" style="margin-bottom:12px;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px;">
        <div>
          <h2 style="font-family:var(--display);font-weight:800;color:var(--text);margin-bottom:6px;">Intelligent Whiteboard</h2>
          <p style="color:var(--text-dim);font-size:11px;">Sketch study maps or paste and render Mermaid diagrams directly from the AI tutor.</p>
        </div>
        <div style="display:flex;gap:10px;align-items:center;">
          <span id="wb-unsaved-badge" style="font-size:10px;font-family:var(--mono);color:var(--orange);display:${this.hasUnsavedChanges ? 'inline' : 'none'};">● Unsaved Changes</span>
          <button id="wb-save-btn" style="background:var(--accent);color:var(--bg);border:none;padding:6px 12px;border-radius:var(--radius);cursor:pointer;font-family:var(--mono);font-size:11px;font-weight:bold;">Save Canvas</button>
          
          <select id="wb-export-format" style="background:var(--bg3);border:1px solid var(--border);color:var(--text);font-family:var(--mono);font-size:11px;padding:5px;border-radius:var(--radius);">
            <option value="png">PNG Image</option>
            <option value="pdf">PDF Doc</option>
          </select>
          <button id="wb-export-btn" style="background:none;border:1px solid var(--accent);color:var(--accent);padding:5px 12px;border-radius:var(--radius);cursor:pointer;font-family:var(--mono);font-size:11px;font-weight:bold;">Export</button>
        </div>
      </div>

      <div style="display:grid;grid-template-columns:1fr 280px;gap:16px;width:100%;height:calc(100vh - 150px);overflow:hidden;">
        <!-- Left: Workspace Controls + Canvas -->
        <div style="display:flex;flex-direction:column;gap:10px;height:100%;overflow:hidden;">
          <!-- Toolbar -->
          <div style="display:flex;align-items:center;justify-content:space-between;background:var(--bg2);border:1px solid var(--border);border-radius:var(--radius);padding:8px 12px;flex-wrap:wrap;gap:8px;">
            <div style="display:flex;align-items:center;gap:6px;">
              <button class="tool-btn" data-tool="pen" title="Freehand Pen" style="background:var(--accent);color:var(--bg);border:none;width:28px;height:28px;border-radius:4px;cursor:pointer;font-size:14px;">✏️</button>
              <button class="tool-btn" data-tool="highlighter" title="Highlighter" style="background:none;border:1px solid var(--border);color:var(--text);width:28px;height:28px;border-radius:4px;cursor:pointer;font-size:14px;">🖍️</button>
              <button class="tool-btn" data-tool="eraser" title="Eraser" style="background:none;border:1px solid var(--border);color:var(--text);width:28px;height:28px;border-radius:4px;cursor:pointer;font-size:14px;">🧹</button>
              <span style="border-right:1px solid var(--border);height:20px;margin:0 4px;"></span>
              <button class="tool-btn" data-tool="line" title="Straight Line" style="background:none;border:1px solid var(--border);color:var(--text);width:28px;height:28px;border-radius:4px;cursor:pointer;font-size:14px;">➖</button>
              <button class="tool-btn" data-tool="arrow" title="Arrow" style="background:none;border:1px solid var(--border);color:var(--text);width:28px;height:28px;border-radius:4px;cursor:pointer;font-size:14px;">↗️</button>
              <button class="tool-btn" data-tool="rectangle" title="Rectangle" style="background:none;border:1px solid var(--border);color:var(--text);width:28px;height:28px;border-radius:4px;cursor:pointer;font-size:14px;">⬛</button>
              <button class="tool-btn" data-tool="circle" title="Circle" style="background:none;border:1px solid var(--border);color:var(--text);width:28px;height:28px;border-radius:4px;cursor:pointer;font-size:14px;">⚪</button>
              <button class="tool-btn" data-tool="text" title="Text Note" style="background:none;border:1px solid var(--border);color:var(--text);width:28px;height:28px;border-radius:4px;cursor:pointer;font-size:14px;">🔤</button>
            </div>

            <div style="display:flex;align-items:center;gap:12px;">
              <!-- Color picker -->
              <div style="display:flex;gap:4px;align-items:center;">
                <span style="font-size:9px;color:var(--text-dim);font-weight:bold;">COLOR</span>
                <input type="color" id="wb-color-picker" value="#00c8ff" style="border:none;background:none;width:24px;height:24px;cursor:pointer;" />
              </div>

              <!-- Stroke width -->
              <div style="display:flex;align-items:center;gap:4px;">
                <span style="font-size:9px;color:var(--text-dim);font-weight:bold;">SIZE</span>
                <select id="wb-stroke-size" style="background:var(--bg3);border:1px solid var(--border);color:var(--text);font-family:var(--mono);font-size:10px;padding:4px;border-radius:var(--radius);">
                  <option value="2">2px</option>
                  <option value="4" selected>4px</option>
                  <option value="8">8px</option>
                  <option value="12">12px</option>
                </select>
              </div>

              <!-- Undo/Redo -->
              <div style="display:flex;gap:4px;">
                <button id="wb-undo-btn" title="Undo" style="background:none;border:1px solid var(--border);color:var(--text);padding:4px 8px;border-radius:4px;cursor:pointer;font-size:11px;">↩️</button>
                <button id="wb-redo-btn" title="Redo" style="background:none;border:1px solid var(--border);color:var(--text);padding:4px 8px;border-radius:4px;cursor:pointer;font-size:11px;">↪️</button>
                <button id="wb-clear-btn" title="Clear Canvas" style="background:none;border:1px solid var(--border);color:var(--red);padding:4px 8px;border-radius:4px;cursor:pointer;font-size:11px;font-weight:bold;">Clear</button>
              </div>
            </div>
          </div>

          <!-- Canvas Viewport Box -->
          <div style="flex:1;border:1px solid var(--border);border-radius:var(--radius-lg);position:relative;overflow:hidden;background:#fff;box-shadow:inset 0 4px 20px rgba(0,0,0,0.05);">
            <canvas id="whiteboard-canvas" width="1000" height="750" style="position:absolute;top:0;left:0;cursor:crosshair;"></canvas>
            
            <!-- Floating zoom indicators -->
            <div style="position:absolute;bottom:14px;right:14px;background:var(--bg2);border:1px solid var(--border);border-radius:20px;padding:4px 10px;font-size:9px;font-family:var(--mono);color:var(--text);display:flex;gap:8px;align-items:center;">
              <button id="zoom-out-btn" style="background:none;border:none;color:var(--text);cursor:pointer;font-weight:bold;">-</button>
              <span id="zoom-label">100%</span>
              <button id="zoom-in-btn" style="background:none;border:none;color:var(--text);cursor:pointer;font-weight:bold;">+</button>
            </div>
          </div>
        </div>

        <!-- Right: Mermaid Diagram Integration -->
        <div style="display:flex;flex-direction:column;gap:14px;height:100%;overflow-y:auto;">
          <sentio-card title="🧜‍♀️ Mermaid Render Engine">
            <p style="font-size:10px;color:var(--text-dim);line-height:1.4;margin-bottom:10px;">Paste a flow diagram generated by your AI tutor to automatically render it as editable vector shapes.</p>
            <textarea id="mermaid-code-input" placeholder="graph TD&#10;  A[Tutor] --> B[RAG]&#10;  B --> C[Whiteboard]" style="width:100%;height:160px;background:var(--bg3);border:1px solid var(--border);border-radius:var(--radius);padding:8px;color:var(--text);font-family:var(--mono);font-size:10px;outline:none;resize:vertical;"></textarea>
            <button id="render-mermaid-btn" style="margin-top:12px;width:100%;background:var(--accent);color:var(--bg);border:none;padding:10px;border-radius:var(--radius);font-family:var(--mono);font-size:11px;font-weight:bold;cursor:pointer;">
              Render Flowchart Shapes
            </button>
          </sentio-card>
          
          <sentio-card title="💡 Annotations & Snippets">
            <p style="font-size:10px;color:var(--text-dim);line-height:1.4;">Drag text blocks, cite sources, or type text note shapes on the canvas to annotate your concepts.</p>
          </sentio-card>
        </div>
      </div>
    `;
  }

  initCanvas() {
    this.canvas = this.container.querySelector('#whiteboard-canvas');
    this.ctx = this.canvas.getContext('2d');

    // Draw initial grid
    this.redraw();

    // Event bindings
    this.canvas.onmousedown = (e) => this.handleMouseDown(e);
    this.canvas.onmousemove = (e) => this.handleMouseMove(e);
    this.canvas.onmouseup = (e) => this.handleMouseUp(e);

    // Save and export
    this.container.querySelector('#wb-save-btn').onclick = () => this.saveWhiteboard(false);
    this.container.querySelector('#wb-export-btn').onclick = () => this.exportWhiteboard();

    // Toolbar select
    this.container.querySelectorAll('.tool-btn').forEach((btn) => {
      btn.onclick = (e) => {
        this.container.querySelectorAll('.tool-btn').forEach((b) => {
          b.style.background = 'none';
          b.style.border = '1px solid var(--border)';
          b.style.color = 'var(--text)';
        });

        const tool = e.currentTarget.dataset.tool;
        this.currentTool = tool;
        e.currentTarget.style.background = 'var(--accent)';
        e.currentTarget.style.color = 'var(--bg)';
        e.currentTarget.style.border = 'none';
      };
    });

    // Undo/Redo/Clear
    this.container.querySelector('#wb-undo-btn').onclick = () => this.undo();
    this.container.querySelector('#wb-redo-btn').onclick = () => this.redo();
    this.container.querySelector('#wb-clear-btn').onclick = () => this.clearCanvas();

    // Zoom bindings
    this.container.querySelector('#zoom-in-btn').onclick = () => this.adjustZoom(0.1);
    this.container.querySelector('#zoom-out-btn').onclick = () => this.adjustZoom(-0.1);

    // Mermaid trigger
    this.container.querySelector('#render-mermaid-btn').onclick = () => this.renderMermaid();

    // Sync preferences
    this.container.querySelector('#wb-color-picker').onchange = (e) => {
      this.currentColor = e.target.value;
    };
    this.container.querySelector('#wb-stroke-size').onchange = (e) => {
      this.currentWidth = parseInt(e.target.value, 10);
    };
  }

  adjustZoom(amount) {
    this.zoomLevel = Math.max(0.5, Math.min(2.0, this.zoomLevel + amount));
    this.container.querySelector('#zoom-label').textContent =
      Math.round(this.zoomLevel * 100) + '%';
    this.redraw();
  }

  getMousePos(e) {
    const rect = this.canvas.getBoundingClientRect();
    // Account for zoom and bounding client size scale
    const x = (e.clientX - rect.left) / this.zoomLevel;
    const y = (e.clientY - rect.top) / this.zoomLevel;
    return { x, y };
  }

  handleMouseDown(e) {
    this.isDrawing = true;
    const pos = this.getMousePos(e);
    this.startX = pos.x;
    this.startY = pos.y;
    this.currentPoints = [[pos.x, pos.y]];

    if (this.currentTool === 'text') {
      this.isDrawing = false;
      this.promptTextInput(pos.x, pos.y);
    }
  }

  handleMouseMove(e) {
    if (!this.isDrawing) return;
    const pos = this.getMousePos(e);

    if (this.currentTool === 'pen' || this.currentTool === 'highlighter') {
      this.currentPoints.push([pos.x, pos.y]);
      this.redraw();

      // Draw temporary path segment
      this.ctx.save();
      this.ctx.scale(this.zoomLevel, this.zoomLevel);
      this.ctx.beginPath();
      this.ctx.strokeStyle =
        this.currentTool === 'highlighter'
          ? this.hexToRGBA(this.currentColor, 0.4)
          : this.currentColor;
      this.ctx.lineWidth = this.currentWidth;
      this.ctx.lineCap = 'round';
      this.ctx.lineJoin = 'round';
      this.ctx.moveTo(this.currentPoints[0][0], this.currentPoints[0][1]);
      for (let i = 1; i < this.currentPoints.length; i++) {
        this.ctx.lineTo(this.currentPoints[i][0], this.currentPoints[i][1]);
      }
      this.ctx.stroke();
      this.ctx.restore();
    } else if (['line', 'arrow', 'rectangle', 'circle'].includes(this.currentTool)) {
      // Draw shapes preview
      this.redraw();
      this.ctx.save();
      this.ctx.scale(this.zoomLevel, this.zoomLevel);
      this.ctx.strokeStyle = this.currentColor;
      this.ctx.lineWidth = this.currentWidth;
      this.ctx.beginPath();

      if (this.currentTool === 'line') {
        this.ctx.moveTo(this.startX, this.startY);
        this.ctx.lineTo(pos.x, pos.y);
      } else if (this.currentTool === 'arrow') {
        this.ctx.moveTo(this.startX, this.startY);
        this.ctx.lineTo(pos.x, pos.y);
      } else if (this.currentTool === 'rectangle') {
        this.ctx.rect(this.startX, this.startY, pos.x - this.startX, pos.y - this.startY);
      } else if (this.currentTool === 'circle') {
        const dx = pos.x - this.startX;
        const dy = pos.y - this.startY;
        const r = Math.sqrt(dx * dx + dy * dy);
        this.ctx.arc(this.startX, this.startY, r, 0, 2 * Math.PI);
      }
      this.ctx.stroke();
      this.ctx.restore();
    } else if (this.currentTool === 'eraser') {
      // Remove shapes intersecting pos
      const prevLength = this.shapes.length;
      this.shapes = this.shapes.filter((s) => !this.isPointInShape(pos.x, pos.y, s));
      if (this.shapes.length !== prevLength) {
        this.markUnsaved();
        this.redraw();
      }
    }
  }

  handleMouseUp(e) {
    if (!this.isDrawing) return;
    this.isDrawing = false;
    const pos = this.getMousePos(e);

    const color =
      this.currentTool === 'highlighter'
        ? this.hexToRGBA(this.currentColor, 0.4)
        : this.currentColor;

    let newShape = null;

    if (this.currentTool === 'pen' || this.currentTool === 'highlighter') {
      if (this.currentPoints.length >= 2) {
        newShape = {
          type: 'line',
          points: this.currentPoints,
          color,
          strokeWidth: this.currentWidth,
        };
      }
    } else if (this.currentTool === 'line') {
      newShape = {
        type: 'line',
        points: [
          [this.startX, this.startY],
          [pos.x, pos.y],
        ],
        color,
        strokeWidth: this.currentWidth,
      };
    } else if (this.currentTool === 'arrow') {
      newShape = {
        type: 'arrow',
        points: [
          [this.startX, this.startY],
          [pos.x, pos.y],
        ],
        color,
        strokeWidth: this.currentWidth,
      };
    } else if (this.currentTool === 'rectangle') {
      newShape = {
        type: 'rectangle',
        x: Math.min(this.startX, pos.x),
        y: Math.min(this.startY, pos.y),
        width: Math.abs(pos.x - this.startX),
        height: Math.abs(pos.y - this.startY),
        color,
        strokeWidth: this.currentWidth,
      };
    } else if (this.currentTool === 'circle') {
      const dx = pos.x - this.startX;
      const dy = pos.y - this.startY;
      const r = Math.sqrt(dx * dx + dy * dy);
      newShape = {
        type: 'circle',
        x: this.startX - r,
        y: this.startY - r,
        width: r * 2,
        height: r * 2,
        color,
        strokeWidth: this.currentWidth,
      };
    }

    if (newShape) {
      this.shapes.push(newShape);
      this.undoStack.push(JSON.parse(JSON.stringify(this.shapes)));
      this.redoStack = [];
      this.markUnsaved();
      this.redraw();
    }
  }

  isPointInShape(px, py, shape) {
    if (shape.type === 'rectangle') {
      return (
        px >= shape.x &&
        px <= shape.x + shape.width &&
        py >= shape.y &&
        py <= shape.y + shape.height
      );
    }
    if (shape.type === 'circle') {
      const r = shape.width / 2;
      const cx = shape.x + r;
      const cy = shape.y + r;
      const dx = px - cx;
      const dy = py - cy;
      return dx * dx + dy * dy <= r * r;
    }
    // Simple pen/line check: bounding box intersection
    if (shape.points) {
      for (const p of shape.points) {
        const dx = px - p[0];
        const dy = py - p[1];
        if (dx * dx + dy * dy < 120) return true;
      }
    }
    return false;
  }

  promptTextInput(x, y) {
    const text = prompt('Enter text note:');
    if (text) {
      this.shapes.push({
        type: 'text',
        x,
        y,
        text,
        color: this.currentColor,
        fontSize: 16,
      });
      this.undoStack.push(JSON.parse(JSON.stringify(this.shapes)));
      this.markUnsaved();
      this.redraw();
    }
  }

  hexToRGBA(hex, alpha) {
    const r = parseInt(hex.slice(1, 3), 16);
    const g = parseInt(hex.slice(3, 5), 16);
    const b = parseInt(hex.slice(5, 7), 16);
    return `rgba(${r}, ${g}, ${b}, ${alpha})`;
  }

  redraw() {
    this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);

    // Draw Grid Background
    this.ctx.save();
    this.ctx.strokeStyle = '#F0F0F0';
    this.ctx.lineWidth = 1;
    const grid = 40 * this.zoomLevel;
    for (let x = 0; x < this.canvas.width; x += grid) {
      this.ctx.beginPath();
      this.ctx.moveTo(x, 0);
      this.ctx.lineTo(x, this.canvas.height);
      this.ctx.stroke();
    }
    for (let y = 0; y < this.canvas.height; y += grid) {
      this.ctx.beginPath();
      this.ctx.moveTo(0, y);
      this.ctx.lineTo(this.canvas.width, y);
      this.ctx.stroke();
    }
    this.ctx.restore();

    // Draw Vector Shapes
    this.ctx.save();
    this.ctx.scale(this.zoomLevel, this.zoomLevel);

    this.shapes.forEach((s) => {
      this.ctx.strokeStyle = s.color;
      this.ctx.lineWidth = s.strokeWidth || 2;
      this.ctx.lineCap = 'round';
      this.ctx.lineJoin = 'round';

      if (s.type === 'line' && s.points) {
        this.ctx.beginPath();
        this.ctx.moveTo(s.points[0][0], s.points[0][1]);
        for (let i = 1; i < s.points.length; i++) {
          this.ctx.lineTo(s.points[i][0], s.points[i][1]);
        }
        this.ctx.stroke();
      } else if (s.type === 'arrow' && s.points) {
        this.ctx.beginPath();
        const p1 = s.points[0];
        const p2 = s.points[1];
        this.ctx.moveTo(p1[0], p1[1]);
        this.ctx.lineTo(p2[0], p2[1]);
        this.ctx.stroke();
        this.drawArrowhead(p1[0], p1[1], p2[0], p2[1], s.color, s.strokeWidth || 2);
      } else if (s.type === 'rectangle') {
        this.ctx.beginPath();
        this.ctx.rect(s.x, s.y, s.width, s.height);
        this.ctx.stroke();
      } else if (s.type === 'circle') {
        this.ctx.beginPath();
        const r = s.width / 2;
        this.ctx.arc(s.x + r, s.y + r, r, 0, 2 * Math.PI);
        this.ctx.stroke();
      } else if (s.type === 'text') {
        this.ctx.fillStyle = s.color;
        this.ctx.font = `${s.fontSize || 16}px JetBrains Mono`;
        this.ctx.fillText(s.text, s.x, s.y);
      }
    });

    this.ctx.restore();
  }

  drawArrowhead(x1, y1, x2, y2, color, strokeWidth) {
    const dx = x2 - x1;
    const dy = y2 - y1;
    const angle = Math.atan2(dy, dx);
    const len = 12;
    const arrowAngle = Math.PI / 6;

    this.ctx.beginPath();
    this.ctx.fillStyle = color;
    this.ctx.moveTo(x2, y2);
    this.ctx.lineTo(
      x2 - len * Math.cos(angle - arrowAngle),
      y2 - len * Math.sin(angle - arrowAngle),
    );
    this.ctx.lineTo(
      x2 - len * Math.cos(angle + arrowAngle),
      y2 - len * Math.sin(angle + arrowAngle),
    );
    this.ctx.closePath();
    this.ctx.fill();
  }

  undo() {
    if (this.undoStack.length > 0) {
      const last = this.undoStack.pop();
      this.redoStack.push(JSON.parse(JSON.stringify(this.shapes)));
      this.shapes =
        this.undoStack.length > 0
          ? JSON.parse(JSON.stringify(this.undoStack[this.undoStack.length - 1]))
          : [];
      this.markUnsaved();
      this.redraw();
    }
  }

  redo() {
    if (this.redoStack.length > 0) {
      const next = this.redoStack.pop();
      this.undoStack.push(JSON.parse(JSON.stringify(this.shapes)));
      this.shapes = next;
      this.markUnsaved();
      this.redraw();
    }
  }

  clearCanvas() {
    if (confirm('Clear all drawings from the canvas?')) {
      this.shapes = [];
      this.undoStack.push([]);
      this.redoStack = [];
      this.markUnsaved();
      this.redraw();
    }
  }

  markUnsaved() {
    this.hasUnsavedChanges = true;
    const badge = this.container.querySelector('#wb-unsaved-badge');
    if (badge) badge.style.display = 'inline';
  }

  async saveWhiteboard(isAutosave = false) {
    const activeSessionId = store.getState('activeSessionId');
    if (!activeSessionId) {
      if (!isAutosave) toast('Please start or resume a tutoring session before saving.', true);
      return;
    }

    try {
      await sentioAPI.post('/whiteboards/sessions', {
        whiteboard_id: this.whiteboardId,
        student_id: this.studentId,
        session_id: activeSessionId,
        title: this.title,
        canvas_state: {
          width: this.canvas.width,
          height: this.canvas.height,
          shapes: this.shapes,
        },
      });

      this.hasUnsavedChanges = false;
      const badge = this.container.querySelector('#wb-unsaved-badge');
      if (badge) badge.style.display = 'none';

      if (!isAutosave) toast('Whiteboard synced successfully.');
    } catch (e) {
      if (!isAutosave) toast('Save failed: ' + e.message, true);
    }
  }

  async exportWhiteboard() {
    const format = this.container.querySelector('#wb-export-format').value;

    // First, save canvas state to ensure latest vector rendering on Pillow
    await this.saveWhiteboard(true);

    toast('Exporting diagram stream...');

    try {
      const res = await sentioAPI.request(`/whiteboards/${this.whiteboardId}/export`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ format }),
      });

      // Download response blob
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const dlAnchor = document.createElement('a');
      dlAnchor.href = url;
      dlAnchor.download = `sentio_whiteboard_${this.whiteboardId}.${format}`;
      document.body.appendChild(dlAnchor);
      dlAnchor.click();
      dlAnchor.remove();
      window.URL.revokeObjectURL(url);

      toast('Export complete!');
    } catch (e) {
      toast('Export failed: ' + e.message, true);
    }
  }

  async renderMermaid() {
    const code = this.container.querySelector('#mermaid-code-input').value.trim();
    if (!code) {
      toast('Mermaid markup cannot be empty', true);
      return;
    }

    store.setState('loading', true);
    try {
      const res = await sentioAPI.post('/whiteboards/mermaid', {
        mermaid_code: code,
      });

      if (res.shapes && res.shapes.length > 0) {
        this.shapes = [...this.shapes, ...res.shapes];
        this.undoStack.push(JSON.parse(JSON.stringify(this.shapes)));
        this.markUnsaved();
        this.redraw();
        toast('Diagram flowchart rendered successfully!');
      } else {
        toast('Parsed 0 shapes. Check flowchart syntax.', true);
      }
    } catch (e) {
      toast('Mermaid parse failed: ' + e.message, true);
    } finally {
      store.setState('loading', false);
    }
  }
}
