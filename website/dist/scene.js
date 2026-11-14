// A conceptual scroll narrative, not a simulation of molecular chemistry.
import {encode} from './encoding.js';
const host = document.querySelector('#molecule');
const story = document.querySelector('.helix-scroll');
const reduced = matchMedia('(prefers-reduced-motion: reduce)');
const pause = document.querySelector('#motion');
const status = document.querySelector('#strand-status');
const explanation = document.querySelector('#strand-explanation');
const progressBar = document.querySelector('#strand-progress');
const sequence = encode(new TextEncoder().encode('DNA DNA'));
let paused = false;
let target = 0;
let shown = 0;
let lastStage = -1;
const clamp = value => Math.max(0, Math.min(1, value));
const smooth = value => { const t = clamp(value); return t*t*(3-2*t); };
function scrollProgress() {
  const rect = story.getBoundingClientRect();
  target = reduced.matches ? 1 : clamp(-rect.top / Math.max(1, story.offsetHeight-innerHeight));
}
function labelButton() {
  pause.textContent = paused ? 'Resume animation ▷' : 'Pause animation Ⅱ';
  pause.setAttribute('aria-pressed', String(paused));
  pause.hidden = reduced.matches;
}
pause.addEventListener('click', () => { paused = !paused; labelButton(); });
addEventListener('scroll', scrollProgress, {passive:true});
addEventListener('resize', scrollProgress);
reduced.addEventListener('change', () => { scrollProgress(); labelButton(); });
function updateNarrative(progress) {
  host.style.setProperty('--unfold', progress);
  progressBar.style.transform = `scaleX(${progress})`;
  const stage = progress < .25 ? 0 : progress < .78 ? 1 : 2;
  if (stage === lastStage) return;
  lastStage = stage;
  status.textContent = ['01 / TWO STRANDS, ONE DOUBLE HELIX', '02 / FOLLOW ONE STRAND', '03 / THE ORDER OF THE LETTERS IS THE DATA'][stage];
  explanation.textContent = [
    'DNA has two complementary strands. Scroll to follow one of them.',
    'As the shape opens, focus on the individual bases along one strand.',
    'A, C, G and T form a sequence. Helix represents file bytes in the order of these letters.'
  ][stage];
}
scrollProgress(); labelButton(); updateNarrative(target);
async function start() {
  try {
    const THREE = await import('./vendor/three.module.js');
    const renderer = new THREE.WebGLRenderer({alpha:true, antialias:true});
    renderer.setPixelRatio(Math.min(devicePixelRatio, 1.7));
    renderer.setClearColor(0,0);
    renderer.domElement.setAttribute('aria-hidden','true');
    renderer.domElement.style.touchAction = 'pan-y';
    host.prepend(renderer.domElement);
    const world = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(36,1,.1,100);
    camera.position.z = 19;
    world.add(new THREE.AmbientLight(0xffffff,2));
    const light = new THREE.DirectionalLight(0xfff8df,3);
    light.position.set(5,8,8); world.add(light);
    const group = new THREE.Group(); world.add(group);
    const colors = {A:0x79986c,C:0xbb946b,G:0xd5b85c,T:0x688e91};
    const complement = {A:'T',T:'A',C:'G',G:'C'};
    const beadGeometry = new THREE.SphereGeometry(.14,14,10);
    const linkGeometry = new THREE.CylinderGeometry(1,1,1,8);
    const mainMaterials = Object.fromEntries(Object.entries(colors).map(([b,color]) => [b,new THREE.MeshStandardMaterial({color,roughness:.55})]));
    const otherMaterials = Object.fromEntries(Object.entries(colors).map(([b,color]) => [b,new THREE.MeshStandardMaterial({color,roughness:.55,transparent:true})]));
    const railMaterial = new THREE.MeshStandardMaterial({color:0x849b73,roughness:.6});
    const otherRailMaterial = railMaterial.clone(); otherRailMaterial.transparent = true;
    const bondMaterial = new THREE.MeshStandardMaterial({color:0xd2c5a7,transparent:true,roughness:.6});
    const count = 24;
    const points = [[],[]]; const beads = [[],[]]; const rails = [[],[]]; const bonds = []; const labels = [];
    const unitY = new THREE.Vector3(0,1,0);
    const delta = new THREE.Vector3();
    function link(material) { const mesh = new THREE.Mesh(linkGeometry,material); group.add(mesh); return mesh; }
    function fit(mesh,a,b,radius) {
      delta.subVectors(b,a);
      mesh.position.copy(a).add(b).multiplyScalar(.5);
      mesh.scale.set(radius, Math.max(.0001,delta.length()),radius);
      mesh.quaternion.setFromUnitVectors(unitY,delta.normalize());
    }
    const textures = {};
    function letter(base) {
      if (!textures[base]) {
        const canvas = document.createElement('canvas'); canvas.width=128; canvas.height=128;
        const ctx = canvas.getContext('2d');
        ctx.fillStyle='#273d30'; ctx.font='600 88px sans-serif'; ctx.textAlign='center'; ctx.textBaseline='middle';
        ctx.fillText(base,64,68);
        textures[base] = new THREE.CanvasTexture(canvas);
      }
      const sprite = new THREE.Sprite(new THREE.SpriteMaterial({map:textures[base],transparent:true,depthTest:false}));
      sprite.scale.set(.34,.34,1); group.add(sprite); return sprite;
    }
    for(let i=0;i<count;i++) {
      for(let strand=0;strand<2;strand++) {
        points[strand].push(new THREE.Vector3());
        const base = strand ? complement[sequence[i]] : sequence[i];
        const mesh = new THREE.Mesh(beadGeometry,(strand ? otherMaterials : mainMaterials)[base]);
        group.add(mesh); beads[strand].push(mesh);
        if(i) rails[strand].push(link(strand ? otherRailMaterial : railMaterial));
      }
      bonds.push(link(bondMaterial)); labels.push(letter(sequence[i]));
    }
    host.querySelector('.fallback').style.display='none';
    host.classList.add('has-webgl');
    const observer = new ResizeObserver(() => {
      const w=host.clientWidth,h=host.clientHeight;
      renderer.setSize(w,h); camera.aspect=w/h; camera.updateProjectionMatrix();
    }); observer.observe(host);
    let drag=false, x=0, rotation=0;
    renderer.domElement.addEventListener('pointerdown',e=>{drag=true;x=e.clientX;renderer.domElement.setPointerCapture(e.pointerId);});
    renderer.domElement.addEventListener('pointermove',e=>{if(drag&&!paused&&!reduced.matches){rotation+=(e.clientX-x)*.012;x=e.clientX;}});
    renderer.domElement.addEventListener('pointerup',()=>drag=false);
    renderer.domElement.addEventListener('pointercancel',()=>drag=false);
    let visible=true;
    new IntersectionObserver(entries=>visible=entries[0].isIntersecting).observe(host);
    let last=0;
    renderer.setAnimationLoop(time=>{
      const dt=Math.min((time-last)/1000,.05); last=time;
      if(!visible||document.hidden) return;
      if(reduced.matches) shown=1;
      else if(!paused) { shown+=(target-shown)*(1-Math.exp(-dt*12)); if(!drag)rotation+=dt*.18; }
      const progress=smooth(shown);
      group.rotation.set(0,rotation*(1-progress),-.3*(1-progress));
      for(let i=0;i<count;i++) {
        // The opening propagates along the helix before it straightens completely.
        const local=smooth(shown*1.3-(i/(count-1))*.3);
        const angle=i*.42;
        for(let strand=0;strand<2;strand++) {
          const sign=strand ? -1 : 1;
          const point=points[strand][i];
          const helixX=sign*Math.cos(angle)*1.3;
          const helixY=(i-(count-1)/2)*.35;
          const helixZ=sign*Math.sin(angle)*1.3;
          const lineX=(i-(count-1)/2)*.32;
          point.set(helixX*(1-local)+lineX*local,
            helixY*(1-local)+(strand ? 3*local : 0),helixZ*(1-local));
          beads[strand][i].position.copy(point);
          if(i)fit(rails[strand][i-1],points[strand][i-1],point,.04);
        }
        fit(bonds[i],points[0][i],points[1][i],.045);
        labels[i].position.copy(points[0][i]); labels[i].position.y-=.43;
        labels[i].material.opacity=smooth((local-.45)/.45);
      }
      const fade=1-smooth((shown-.12)/.7);
      otherRailMaterial.opacity=fade; bondMaterial.opacity=1-smooth(shown/.55);
      Object.values(otherMaterials).forEach(m=>m.opacity=fade);
      updateNarrative(shown); renderer.render(world,camera);
    });
    renderer.domElement.addEventListener('webglcontextlost',event=>{
      event.preventDefault(); renderer.setAnimationLoop(null);
      renderer.domElement.style.display='none'; host.classList.remove('has-webgl'); fallback();
    });
  } catch { fallback(); }
}
function fallback() {
  pause.hidden=true;
  // Keep the same story available as text and a static sequence without WebGL.
  const tick=()=>{updateNarrative(reduced.matches ? 1 : target);requestAnimationFrame(tick);}; tick();
}
start();
