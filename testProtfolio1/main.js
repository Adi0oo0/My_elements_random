// Nav active state -----------------------------------------------------
(function(){
  const page = document.body.getAttribute('data-page');
  document.querySelectorAll('.axis-nav a').forEach(a=>{
    if(a.getAttribute('data-page') === page) a.classList.add('active');
  });
})();

// Mobile nav toggle ------------------------------------------------------
(function(){
  const btn = document.querySelector('.nav-toggle');
  const nav = document.querySelector('.axis-nav');
  if(!btn || !nav) return;
  btn.addEventListener('click', ()=>{
    nav.classList.toggle('open');
  });
  nav.querySelectorAll('a').forEach(a=>a.addEventListener('click', ()=> nav.classList.remove('open')));
})();

// Scroll reveal ------------------------------------------------------
(function(){
  const items = document.querySelectorAll('.reveal');
  if(!items.length) return;
  const io = new IntersectionObserver((entries)=>{
    entries.forEach(e=>{
      if(e.isIntersecting){ e.target.classList.add('in'); io.unobserve(e.target); }
    });
  }, { threshold: 0.15 });
  items.forEach(i=> io.observe(i));
})();

// Copy email to clipboard ------------------------------------------------------
(function(){
  const btn = document.querySelector('[data-copy-email]');
  if(!btn) return;
  btn.addEventListener('click', async ()=>{
    const email = btn.getAttribute('data-copy-email');
    try{
      await navigator.clipboard.writeText(email);
      const original = btn.textContent;
      btn.textContent = 'copied ✓';
      setTimeout(()=> btn.textContent = original, 1800);
    }catch(e){ /* clipboard unavailable — mailto still works */ }
  });
})();
