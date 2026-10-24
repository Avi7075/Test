(async () => {
  const sources = await window.picker.sources();
  for (const s of sources) {
    const b = document.createElement('button');
    b.className = 'src';
    const img = document.createElement('img');
    img.src = s.thumb;
    const name = document.createElement('span');
    name.textContent = s.name;
    b.append(img, name);
    b.addEventListener('click', () => window.picker.choose(s.id));
    document.getElementById(s.screen ? 'screens' : 'windows').append(b);
  }
  document.getElementById('cancel').addEventListener('click', () => window.picker.choose(null));
  document.addEventListener('keydown', (e) => e.key === 'Escape' && window.picker.choose(null));
})();
