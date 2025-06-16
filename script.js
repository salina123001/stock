const beadCountSelect = document.getElementById('beadCount');
const beadSizeSelect = document.getElementById('beadSize');
const palette = document.getElementById('palette');
const canvas = document.getElementById('braceletCanvas');
const ctx = canvas.getContext('2d');

const crystals = [
  { name: '透明水晶', color: '#ffffff' },
  { name: '粉水晶', color: '#ffc0cb' },
  { name: '紫水晶', color: '#8a2be2' },
  { name: '虎眼石', color: '#d2691e' },
  { name: '綠幽靈', color: '#32cd32' },
  { name: '黃水晶', color: '#ffd700' }
];

let selectedColor = crystals[0].color;
let beadCount = 18;
let beadSize = 8;
let beads = [];

function initSelectors() {
  for (let i = 18; i <= 26; i++) {
    const option = document.createElement('option');
    option.value = i;
    option.textContent = i;
    beadCountSelect.appendChild(option);
  }
  beadCountSelect.value = beadCount;

  for (let i = 6; i <= 14; i++) {
    const option = document.createElement('option');
    option.value = i;
    option.textContent = i;
    beadSizeSelect.appendChild(option);
  }
  beadSizeSelect.value = beadSize;
}

function initPalette() {
  crystals.forEach((c, idx) => {
    const item = document.createElement('div');
    item.className = 'palette-item';
    item.style.backgroundColor = c.color;
    if (idx === 0) item.classList.add('selected');
    item.title = c.name;
    item.addEventListener('click', () => {
      selectedColor = c.color;
      document.querySelectorAll('.palette-item').forEach(p => p.classList.remove('selected'));
      item.classList.add('selected');
    });
    palette.appendChild(item);
  });
}

function updateBeads() {
  beadCount = parseInt(beadCountSelect.value, 10);
  beadSize = parseInt(beadSizeSelect.value, 10);
  beads = new Array(beadCount).fill(null);
  draw();
}

function draw() {
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  const beadRadius = beadSize * 2; // scale mm to pixels
  const radius = canvas.width / 2 - beadRadius - 10;
  for (let i = 0; i < beadCount; i++) {
    const angle = (2 * Math.PI / beadCount) * i - Math.PI / 2;
    const x = canvas.width / 2 + radius * Math.cos(angle);
    const y = canvas.height / 2 + radius * Math.sin(angle);
    ctx.beginPath();
    ctx.arc(x, y, beadRadius, 0, Math.PI * 2);
    ctx.fillStyle = beads[i] || '#dddddd';
    ctx.fill();
    ctx.strokeStyle = '#333';
    ctx.stroke();
  }
}

canvas.addEventListener('click', (e) => {
  const rect = canvas.getBoundingClientRect();
  const x = e.clientX - rect.left;
  const y = e.clientY - rect.top;
  const beadRadius = beadSize * 2;
  const radius = canvas.width / 2 - beadRadius - 10;
  for (let i = 0; i < beadCount; i++) {
    const angle = (2 * Math.PI / beadCount) * i - Math.PI / 2;
    const cx = canvas.width / 2 + radius * Math.cos(angle);
    const cy = canvas.height / 2 + radius * Math.sin(angle);
    const dist = Math.sqrt(Math.pow(x - cx, 2) + Math.pow(y - cy, 2));
    if (dist <= beadRadius) {
      beads[i] = selectedColor;
      draw();
      break;
    }
  }
});

beadCountSelect.addEventListener('change', updateBeads);
beadSizeSelect.addEventListener('change', updateBeads);

initSelectors();
initPalette();
updateBeads();
