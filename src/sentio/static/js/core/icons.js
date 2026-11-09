// Drawn line icons and the Sentio symbol, shared by modules and classic scripts.
(function () {
  const paths = {
    upload: 'M12 15V4M7.5 8.5 12 4l4.5 4.5M5 15v3a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-3',
    file: 'M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8zM14 3v5h5',
    check: 'M5 12.5 9.5 17 19 7.5',
    x: 'M6 6l12 12M18 6 6 18',
    alert: 'M12 4 2.8 19.5h18.4zM12 10v4.5M12 17.4v.1',
    refresh: 'M20 11a8 8 0 1 0-2.3 5.7M20 5v6h-6',
    camera: 'M4 8h3l1.5-2h7L17 8h3v11H4zM15.5 13.5a3.5 3.5 0 1 1-7 0 3.5 3.5 0 1 1 7 0',
    send: 'M5 12h13M13 6l6 6-6 6',
    download: 'M12 4v11M7.5 10.5 12 15l4.5-4.5M5 20h14',
    trash: 'M4 7h16M9.5 7V4.5h5V7M6.5 7l1 13h9l1-13',
    logout: 'M14 4h4a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2h-4M10 16l-4-4 4-4M6 12h10',
    folder: 'M3.5 7a2 2 0 0 1 2-2H10l2 2h6.5a2 2 0 0 1 2 2v8.5a2 2 0 0 1-2 2h-13a2 2 0 0 1-2-2z',
    cards: 'M7 4h11a2 2 0 0 1 2 2v9M4 8h11a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2z',
    done: 'M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM8 12.2l2.8 2.8L16 9.6',
    book: 'M4 5.5A1.5 1.5 0 0 1 5.5 4H11v16H5.5A1.5 1.5 0 0 1 4 18.5zM20 5.5A1.5 1.5 0 0 0 18.5 4H13v16h5.5a1.5 1.5 0 0 0 1.5-1.5z',
  };

  // Returns an inline SVG icon that inherits the surrounding text colour.
  function icon(name, size = 18) {
    const d = paths[name];
    if (!d) return '';
    return `<svg class="icon" width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="${d}"/></svg>`;
  }

  // The Sentio symbol: the wordmark's O, filled, with its page corner turned.
  function symbol(width = 28) {
    const height = Math.round((width * 100) / 140);
    return `<svg class="sentio-symbol" width="${width}" height="${height}" viewBox="0 0 140 100" aria-hidden="true"><path fill="currentColor" d="M14 0H106L140 34V86A14 14 0 0 1 126 100H14A14 14 0 0 1 0 86V14A14 14 0 0 1 14 0Z"/></svg>`;
  }

  window.sentioIcon = icon;
  window.sentioSymbol = symbol;
})();
