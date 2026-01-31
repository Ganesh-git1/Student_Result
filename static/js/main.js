document.addEventListener('DOMContentLoaded', function(){
  const toggle = document.getElementById('navToggle');
  const nav = document.getElementById('mainNav');
  if(toggle && nav){
    toggle.addEventListener('click', function(){
      nav.classList.toggle('show');
    });
    // close menu on outside click (mobile)
    document.addEventListener('click', (e) => {
      if(!nav.contains(e.target) && !toggle.contains(e.target)){
        nav.classList.remove('show');
      }
    });
  }
});
