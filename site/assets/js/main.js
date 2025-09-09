
// navbar scroll shadow
window.addEventListener('scroll', () => {
  const navbar = document.getElementById('navbar');
  if (!navbar) return;
  if (window.scrollY > 50) navbar.classList.add('scrolled');
  else navbar.classList.remove('scrolled');
});

// smooth scroll for hash links on same page
document.querySelectorAll('a[href^="#"]').forEach(a => {
  a.addEventListener('click', e => {
    const href = a.getAttribute('href');
    if (!href || href === '#' || href.length === 1) return;
    const tgt = document.querySelector(href);
    if (tgt) {
      e.preventDefault();
      window.scrollTo({ top: tgt.offsetTop - 80, behavior: 'smooth' });
    }
  });
});

// assessment bars animation (if present)
const strengthBarsContainer = document.getElementById('strengthBars');
if (strengthBarsContainer) {
  const barObserver = new IntersectionObserver(entries => {
    if (entries[0].isIntersecting) {
      const bars = document.querySelectorAll('.strength-bar');
      bars.forEach((bar, index) => {
        const targetWidth = bar.getAttribute('data-width');
        bar.style.setProperty('--target-width', targetWidth + '%');
        setTimeout(() => bar.classList.add('animate'), index * 150);
      });
    }
  }, { threshold: 0.2 });
  barObserver.observe(strengthBarsContainer);
}

// modal controls (index page)
const inquiryModal = document.getElementById('inquiryModal');
const modalOpeners = document.querySelectorAll('[data-open-modal="inquiry"]');
const modalCloser = document.querySelector('[data-close-modal="inquiry"]');
modalOpeners.forEach(btn => btn.addEventListener('click', () => inquiryModal?.classList.add('active')));
modalCloser?.addEventListener('click', () => inquiryModal?.classList.remove('active'));
window.addEventListener('click', e => {
  if (e.target === inquiryModal) inquiryModal.classList.remove('active');
});

// hamburger toggle
const menuBtn = document.getElementById('menuBtn');
const mobileMenu = document.getElementById('mobileMenu');
if(menuBtn && mobileMenu){
  menuBtn.addEventListener('click', ()=>{
    mobileMenu.classList.toggle('hidden');
  });
}
