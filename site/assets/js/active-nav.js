
// set exact-match active nav link
function setActiveNavLink(){
  try{
    const path = window.location.pathname.replace(/\/$/, '') || '/';
    document.querySelectorAll('#navbar a.nav-link').forEach(a=>{
      try{
        const url = new URL(a.getAttribute('href'), location.origin);
        const aPath = url.pathname.replace(/\/$/, '') || '/';
        if(aPath === path){ a.classList.add('border-b-2','border-accent','text-primary'); }
        else { a.classList.remove('border-b-2','border-accent','text-primary'); }
      }catch(e){}
    });
  }catch(e){}
}
document.addEventListener('DOMContentLoaded', setActiveNavLink);
window.addEventListener('popstate', setActiveNavLink);
