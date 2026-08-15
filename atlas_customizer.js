(() => {
  const themes = {
    'ivory-whisper': { accent:'#53161D', accentRgb:'83,22,29', paper:'#FFFBF0', ink:'#211B1C', bg:'#FFFBF0', surface:'rgba(255,253,247,.76)', surface2:'rgba(255,253,247,.88)', text:'#211B1C', muted:'rgba(33,27,28,.58)', border:'rgba(83,22,29,.13)' },
    'deep-sea': { accent:'#156874', accentRgb:'21,104,116', paper:'#EDE6E6', ink:'#101617', bg:'#0e1213', surface:'rgba(20,27,28,.72)', surface2:'rgba(29,37,38,.78)', text:'#F4F6F4', muted:'rgba(237,230,230,.58)', border:'rgba(237,230,230,.10)' },
    'dutch-wine': { accent:'#722F37', accentRgb:'114,47,55', paper:'#EFDFBB', ink:'#2B1819', bg:'#171213', surface:'rgba(36,25,25,.74)', surface2:'rgba(48,32,33,.80)', text:'#F7EEDB', muted:'rgba(239,223,187,.58)', border:'rgba(239,223,187,.12)' },
    'caramel-raisin': { accent:'#C07210', accentRgb:'192,114,16', paper:'#2C1E25', ink:'#160F13', bg:'#141112', surface:'rgba(36,27,28,.74)', surface2:'rgba(47,34,36,.82)', text:'#F8EFE3', muted:'rgba(248,239,227,.56)', border:'rgba(248,239,227,.10)' }
  };

  function applyTheme(name) {
    const t = themes[name] || themes['ivory-whisper'];
    const r = document.documentElement.style;
    document.body.dataset.theme = name;
    r.setProperty('--atlas-accent', t.accent);
    r.setProperty('--atlas-accent-rgb', t.accentRgb);
    r.setProperty('--atlas-paper', t.paper);
    r.setProperty('--atlas-ink', t.ink);
    r.setProperty('--atlas-bg', t.bg);
    r.setProperty('--atlas-surface', t.surface);
    r.setProperty('--atlas-surface-2', t.surface2);
    r.setProperty('--atlas-text', t.text);
    r.setProperty('--atlas-muted', t.muted);
    r.setProperty('--atlas-border', t.border);
    localStorage.setItem('atlas-theme', name);
    document.querySelectorAll('.theme-chip').forEach(b => b.classList.toggle('active', b.dataset.theme === name));
  }

  document.addEventListener('DOMContentLoaded', () => {
    if (!document.querySelector('.theme-dock')) {
      const dock = document.createElement('div');
      dock.className = 'theme-dock';
      dock.setAttribute('aria-label', 'ATLAS theme selector');
      dock.innerHTML = `<span class="theme-dock-label">Theme</span>${Object.keys(themes).map((name, i) => `<button class="theme-chip" data-theme="${name}" title="${name.replace(/-/g,' ')}" aria-label="${name.replace(/-/g,' ')}"></button>`).join('')}`;
      document.body.appendChild(dock);
      dock.addEventListener('click', e => { const b = e.target.closest('.theme-chip'); if (b) applyTheme(b.dataset.theme); });
    }
    applyTheme(localStorage.getItem('atlas-theme') || 'ivory-whisper');
  });
})();
